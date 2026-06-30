"""
News provider — Finnhub is the sole source for both Gold and BTC news,
normalized to a single NewsItem schema with VADER sentiment scoring
applied uniformly so headlines are comparable on the same scale.

Finnhub's /news endpoint returns broad categories ("forex", "crypto",
"general"), not symbol-specific feeds, so a lightweight keyword filter is
applied on top to keep Gold headlines from leaking into BTC's feed and
vice versa.
"""
from abc import ABC, abstractmethod
from datetime import datetime, timezone

import httpx
import structlog
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from app.core.config import Settings
from app.models.schemas import AssetSymbol, NewsItem

logger = structlog.get_logger(__name__)
_analyzer = SentimentIntensityAnalyzer()

_KEYWORDS = {
    AssetSymbol.XAUUSD: ("gold", "xau", "bullion", "precious metal", "fed", "inflation", "interest rate"),
    AssetSymbol.BTCUSD: ("bitcoin", "btc", "crypto", "ethereum", "blockchain"),
}


def score_sentiment(text: str) -> float:
    """Returns compound sentiment score in [-1, 1]."""
    return _analyzer.polarity_scores(text)["compound"]


def _is_relevant(symbol: AssetSymbol, title: str, summary: str) -> bool:
    haystack = f"{title} {summary}".lower()
    return any(keyword in haystack for keyword in _KEYWORDS[symbol])


class NewsProvider(ABC):
    @abstractmethod
    async def get_news(self, symbol: AssetSymbol, limit: int = 20) -> list[NewsItem]:
        raise NotImplementedError


class FinnhubNewsProvider(NewsProvider):
    """Sole news source for both Gold (forex/general category) and BTC (crypto category)."""

    _BASE_URL = "https://finnhub.io/api/v1"

    def __init__(self, settings: Settings):
        self._api_key = settings.finnhub_api_key.get_secret_value()

    async def get_news(self, symbol: AssetSymbol, limit: int = 20) -> list[NewsItem]:
        category = "forex" if symbol == AssetSymbol.XAUUSD else "crypto"
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{self._BASE_URL}/news",
                params={"category": category, "token": self._api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        items = []
        for item in data:
            headline = item.get("headline", "")
            summary = item.get("summary", "")
            if not _is_relevant(symbol, headline, summary):
                continue
            text = f"{headline}. {summary}"
            items.append(
                NewsItem(
                    source=item.get("source", "Finnhub"),
                    title=headline,
                    url=item.get("url", ""),
                    published_at=datetime.fromtimestamp(item.get("datetime", 0), tz=timezone.utc),
                    sentiment_score=score_sentiment(text),
                    related_symbol=symbol,
                )
            )
            if len(items) >= limit:
                break

        # Fallback: if the keyword filter was too strict and nothing matched,
        # return the unfiltered top headlines rather than an empty feed.
        if not items and data:
            for item in data[:limit]:
                text = f"{item.get('headline', '')}. {item.get('summary', '')}"
                items.append(
                    NewsItem(
                        source=item.get("source", "Finnhub"),
                        title=item.get("headline", ""),
                        url=item.get("url", ""),
                        published_at=datetime.fromtimestamp(item.get("datetime", 0), tz=timezone.utc),
                        sentiment_score=score_sentiment(text),
                        related_symbol=symbol,
                    )
                )

        return items


class NewsAggregator:
    """Thin wrapper around the single news provider — kept as its own class
    so routes/decision engine don't need to change if a second source is
    ever added back later."""

    def __init__(self, settings: Settings):
        self._finnhub = FinnhubNewsProvider(settings)

    async def get_news(self, symbol: AssetSymbol, limit: int = 20) -> list[NewsItem]:
        try:
            return await self._finnhub.get_news(symbol, limit)
        except Exception:
            logger.exception("finnhub_news_failed", symbol=symbol)
            return []

    @staticmethod
    def average_sentiment(items: list[NewsItem]) -> float:
        if not items:
            return 0.0
        return sum(i.sentiment_score for i in items) / len(items)
