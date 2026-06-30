"""
Background jobs:
1. One long-lived streaming task per symbol -> publishes ticks to Redis so
   the WebSocket hub can fan them out (one upstream connection, many clients).
2. A periodic APScheduler job that refreshes the cached analysis so REST
   calls are served from cache rather than recomputing on every request.
"""
import asyncio
import json

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.core.config import Settings
from app.models.schemas import AssetSymbol
from app.services.analysis_orchestrator import run_technical_analysis
from app.services.cache_service import CacheService
from app.services.provider_factory import get_provider_for_symbol

logger = structlog.get_logger(__name__)

_TRACKED_SYMBOLS = [AssetSymbol.XAUUSD, AssetSymbol.BTCUSD]
_DEFAULT_TIMEFRAME = "H1"


async def _stream_symbol_to_redis(symbol: AssetSymbol, settings: Settings) -> None:
    """Long-running task: pulls live ticks from the provider, republishes to Redis."""
    provider = get_provider_for_symbol(symbol, settings)
    cache = CacheService(settings)
    channel = f"prices:{symbol.value}"

    while True:
        try:
            async for candle in provider.stream_price(symbol.value):
                await cache.publish(channel, candle.model_dump(mode="json"))
        except Exception:
            logger.exception("price_stream_failed_restarting", symbol=symbol.value)
            await asyncio.sleep(5)  # backoff before reconnecting


async def _refresh_analysis_cache(settings: Settings) -> None:
    cache = CacheService(settings)
    for symbol in _TRACKED_SYMBOLS:
        try:
            provider = get_provider_for_symbol(symbol, settings)
            series = await provider.get_candles(symbol.value, _DEFAULT_TIMEFRAME, 250)
            result = run_technical_analysis(symbol, _DEFAULT_TIMEFRAME, series.candles)
            await cache.set_json(
                f"analysis:{symbol.value}:{_DEFAULT_TIMEFRAME}",
                result.model_dump(mode="json"),
                ttl=settings.analysis_refresh_interval_sec + 30,
            )
        except Exception:
            logger.exception("analysis_refresh_failed", symbol=symbol.value)


def start_background_jobs(settings: Settings) -> tuple[AsyncIOScheduler, list[asyncio.Task]]:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        _refresh_analysis_cache, "interval",
        seconds=settings.analysis_refresh_interval_sec, args=[settings],
        id="refresh_analysis_cache", max_instances=1,
    )
    scheduler.start()

    streaming_tasks = [
        asyncio.create_task(_stream_symbol_to_redis(symbol, settings))
        for symbol in _TRACKED_SYMBOLS
    ]
    return scheduler, streaming_tasks
