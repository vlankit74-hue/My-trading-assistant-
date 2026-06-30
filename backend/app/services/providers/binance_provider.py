"""
Binance provider — used for Bitcoin (BTC/USD, traded as BTCUSDT).
Docs: https://binance-docs.github.io/apidocs/spot/en/

Public market-data endpoints (klines, ticker) don't strictly require auth,
but we sign requests when keys are present to get higher rate limits.
"""
from collections.abc import AsyncIterator
from datetime import datetime, timezone

import httpx
import structlog
import websockets
import json as jsonlib
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import Settings
from app.models.schemas import Candle, CandleSeries
from app.services.providers.base import PriceProvider

logger = structlog.get_logger(__name__)

_BASE_URL = "https://api.binance.com"
_WS_URL = "wss://stream.binance.com:9443/ws"

_SYMBOL_MAP = {"BTCUSD": "BTCUSDT"}

# Map our timeframe strings -> Binance kline interval
_INTERVAL_MAP = {"M15": "15m", "H1": "1h", "H4": "4h", "D1": "1d"}


class BinanceProvider(PriceProvider):
    def __init__(self, settings: Settings):
        self._settings = settings
        self._headers = {}
        if settings.binance_api_key.get_secret_value():
            self._headers["X-MBX-APIKEY"] = settings.binance_api_key.get_secret_value()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=0.5, max=5))
    async def get_candles(self, symbol: str, timeframe: str, count: int) -> CandleSeries:
        pair = _SYMBOL_MAP[symbol]
        interval = _INTERVAL_MAP[timeframe]

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_BASE_URL}/api/v3/klines",
                headers=self._headers,
                params={"symbol": pair, "interval": interval, "limit": count},
            )
            resp.raise_for_status()
            data = resp.json()

        candles = [
            Candle(
                timestamp=datetime.fromtimestamp(k[0] / 1000, tz=timezone.utc),
                open=float(k[1]), high=float(k[2]), low=float(k[3]), close=float(k[4]),
                volume=float(k[5]),
            )
            for k in data
        ]
        return CandleSeries(symbol=symbol, timeframe=timeframe, candles=candles)

    async def get_latest_price(self, symbol: str) -> float:
        pair = _SYMBOL_MAP[symbol]
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{_BASE_URL}/api/v3/ticker/price", params={"symbol": pair}
            )
            resp.raise_for_status()
            return float(resp.json()["price"])

    async def stream_price(self, symbol: str) -> AsyncIterator[Candle]:
        """Streams live trade ticks via Binance's public WebSocket."""
        pair = _SYMBOL_MAP[symbol].lower()
        stream_name = f"{pair}@trade"

        async for ws in websockets.connect(f"{_WS_URL}/{stream_name}"):
            try:
                async for raw in ws:
                    msg = jsonlib.loads(raw)
                    price = float(msg["p"])
                    yield Candle(
                        timestamp=datetime.fromtimestamp(msg["T"] / 1000, tz=timezone.utc),
                        open=price, high=price, low=price, close=price,
                        volume=float(msg.get("q", 0)),
                    )
            except websockets.ConnectionClosed:
                logger.warning("binance_ws_reconnecting", symbol=symbol)
                continue
