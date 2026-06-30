"""
Abstract interface every price provider must implement. Strategy code and
API routes depend only on this interface — never on TwelveDataProvider or
BinanceProvider/TwelveDataProvider directly. This is what makes swapping/adding providers safe.
"""
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

from app.models.schemas import Candle, CandleSeries


class PriceProvider(ABC):
    """Contract for any source of OHLCV candle data and live price ticks."""

    @abstractmethod
    async def get_candles(self, symbol: str, timeframe: str, count: int) -> CandleSeries:
        """Fetch the most recent `count` candles for symbol/timeframe."""
        raise NotImplementedError

    @abstractmethod
    async def stream_price(self, symbol: str) -> AsyncIterator[Candle]:
        """Yield live price ticks/candles as they arrive (WebSocket or polling)."""
        raise NotImplementedError

    @abstractmethod
    async def get_latest_price(self, symbol: str) -> float:
        """Fetch a single current price snapshot (used for cache warm-up / fallback)."""
        raise NotImplementedError
