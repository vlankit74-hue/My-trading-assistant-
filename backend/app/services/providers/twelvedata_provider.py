"""
Twelve Data provider — used for Gold (XAU/USD) AND Bitcoin (BTC/USD).

BTC is routed through Twelve Data rather than Binance because Binance.com
blocks requests from US-based server IPs (HTTP 451, "Unavailable for Legal
Reasons") — and Render's servers run in US datacenters, so every Binance
call failed regardless of the developer's own location. Twelve Data
supports BTC/USD natively via the same time_series endpoint as Gold, and
isn't subject to that restriction, so both assets now share one provider.

Docs: https://twelvedata.com/docs

Twelve Data's REST API covers both historical candles (time_series) and a
live price snapshot (price). It does not offer a free/basic-tier WebSocket
stream the way Binance does, so `stream_price` here polls the price
endpoint on an interval and yields it through the same
AsyncIterator[Candle] contract every other provider uses. Nothing
downstream (WebSocket hub, scheduler) needs to know an asset isn't truly
push-streamed — the interface is identical.

RATE LIMITING: the free/basic plan allows only 8 calls/minute TOTAL across
every endpoint. Two independent streaming loops (Gold + BTC) plus on-demand
REST endpoints (candles/analysis, on a cache miss) can all fire within the
same few seconds of each other with no coordination — each loop "polling
every 30s" in isolation does NOT guarantee the combined call rate stays
under budget. Every network call in this file goes through one shared
module-level AsyncRateLimiter so the aggregate is capped regardless of
which code path triggered the call.
"""
import asyncio
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx
import structlog
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.models.schemas import Candle, CandleSeries
from app.services.providers.base import PriceProvider
from app.services.providers.rate_limiter import AsyncRateLimiter

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.twelvedata.com"

# Map our internal symbol -> Twelve Data symbol
_SYMBOL_MAP = {"XAUUSD": "XAU/USD", "BTCUSD": "BTC/USD"}

# Map our timeframe strings -> Twelve Data interval
_INTERVAL_MAP = {"M15": "15min", "H1": "1h", "H4": "4h", "D1": "1day"}

# Twelve Data's free/basic plan allows only 8 API calls/minute total. We
# cap at 7/min (not 8) to leave a small safety margin for clock drift.
# This single instance is shared by every TwelveDataProvider in the
# process — see module docstring for why per-loop sleeping isn't enough.
_RATE_LIMITER = AsyncRateLimiter(max_calls=7, period_seconds=60)

# Floor for the live-price poll interval. Tunable via
# PRICE_REFRESH_INTERVAL_SEC, but never allowed below this — the real
# protection against bursting the quota is _RATE_LIMITER above, this floor
# just avoids pointlessly queuing up requests that the limiter would have
# to delay anyway.
_MIN_POLL_INTERVAL_SEC = 30


def _should_retry(exc: BaseException) -> bool:
    """Tenacity calls this with the raised exception and retries only if
    it returns True. We retry transient errors (timeouts, 5xx, connection
    issues) but NOT 429 Too Many Requests — retrying a rate-limit error
    immediately just spends more of the same per-minute budget instead of
    waiting for it to reset, which is what the shared rate limiter is for."""
    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429:
        return False
    return True


class TwelveDataProvider(PriceProvider):
    def __init__(self, settings: Settings):
        self._api_key = settings.twelvedata_api_key.get_secret_value()
        self._poll_interval_sec = max(settings.price_refresh_interval_sec, _MIN_POLL_INTERVAL_SEC)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=5),
        retry=retry_if_exception(_should_retry),
    )
    async def get_candles(self, symbol: str, timeframe: str, count: int) -> CandleSeries:
        td_symbol = _SYMBOL_MAP[symbol]
        interval = _INTERVAL_MAP[timeframe]

        await _RATE_LIMITER.acquire()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_BASE_URL}/time_series",
                params={
                    "symbol": td_symbol,
                    "interval": interval,
                    "outputsize": count,
                    "apikey": self._api_key,
                },
            )
            resp.raise_for_status()
            data = resp.json()

        if data.get("status") == "error":
            raise RuntimeError(f"Twelve Data error: {data.get('message')}")

        values = data.get("values", [])
        candles = [
            Candle(
                timestamp=datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if len(v["datetime"]) > 10
                else datetime.strptime(v["datetime"], "%Y-%m-%d").replace(tzinfo=timezone.utc),
                open=float(v["open"]),
                high=float(v["high"]),
                low=float(v["low"]),
                close=float(v["close"]),
                volume=float(v.get("volume", 0) or 0),
            )
            for v in values
        ]
        # Twelve Data returns most-recent-first; our strategy code expects ascending time.
        candles.reverse()
        return CandleSeries(symbol=symbol, timeframe=timeframe, candles=candles)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.5, max=5),
        retry=retry_if_exception(_should_retry),
    )
    async def get_latest_price(self, symbol: str) -> float:
        td_symbol = _SYMBOL_MAP[symbol]
        await _RATE_LIMITER.acquire()
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_BASE_URL}/price",
                params={"symbol": td_symbol, "apikey": self._api_key},
            )
            resp.raise_for_status()
            data = resp.json()
        if "price" not in data:
            raise RuntimeError(f"Twelve Data error fetching price: {data}")
        return float(data["price"])

    async def stream_price(self, symbol: str) -> AsyncIterator[Candle]:
        """
        No native streaming on Twelve Data's free/basic tier, so this polls
        the live price endpoint and yields a pseudo-candle (O=H=L=C=price)
        through the same AsyncIterator[Candle] contract a true tick stream
        would use. Every poll still passes through the shared rate limiter,
        so this loop slows down automatically if other calls (the other
        asset's stream, or REST requests) are also consuming the budget.
        """
        while True:
            try:
                price = await self.get_latest_price(symbol)
                yield Candle(
                    timestamp=datetime.now(timezone.utc),
                    open=price, high=price, low=price, close=price, volume=0,
                )
            except Exception:
                logger.exception("twelvedata_poll_failed", symbol=symbol)
            await asyncio.sleep(self._poll_interval_sec)
