"""
Domain models. These are the contracts every layer (providers, strategy
engine, AI layer, API) speaks. Keeping them centralized means a provider
swap or a new strategy module never has to invent its own shape.
"""
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class AssetSymbol(str, Enum):
    XAUUSD = "XAUUSD"   # Gold
    BTCUSD = "BTCUSD"   # Bitcoin


class Candle(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0


class CandleSeries(BaseModel):
    symbol: AssetSymbol
    timeframe: str  # e.g. "M15", "H1", "H4", "D1"
    candles: list[Candle]


class TrendDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class OrderBlock(BaseModel):
    type: TrendDirection  # bullish OB or bearish OB
    high: float
    low: float
    timestamp: datetime
    mitigated: bool = False


class StructureEvent(BaseModel):
    """A Break of Structure (BOS) or Market Structure Shift (MSS)."""
    kind: str  # "BOS" or "MSS"
    direction: TrendDirection
    level: float
    timestamp: datetime


class CandlestickPattern(BaseModel):
    """A recognized price-action candlestick pattern."""
    name: str  # e.g. "bullish_engulfing", "hammer", "doji", "morning_star"
    direction: TrendDirection  # the signal bias the pattern implies
    timestamp: datetime  # timestamp of the candle the pattern completes on
    strength: float = Field(ge=0.0, le=1.0)  # rough confidence, 0-1, based on pattern quality


class FibonacciLevels(BaseModel):
    swing_high: float
    swing_low: float
    direction: TrendDirection  # direction of the impulse the fib is drawn on
    levels: dict[str, float]  # {"0.236": ..., "0.382": ..., "0.5": ..., "0.618": ..., "0.786": ...}


class IndicatorSnapshot(BaseModel):
    rsi_14: float | None = None
    rsi_divergence: str | None = None  # "bullish_divergence" | "bearish_divergence" | None
    macd: float | None = None
    macd_signal: float | None = None
    macd_crossover: str | None = None  # "bullish_cross" | "bearish_cross" | None
    ema_20: float | None = None
    ema_50: float | None = None
    ema_200: float | None = None
    ema_trend: TrendDirection | None = None


class NewsItem(BaseModel):
    source: str
    title: str
    url: str
    published_at: datetime
    sentiment_score: float = Field(ge=-1.0, le=1.0)  # -1 very negative .. +1 very positive
    related_symbol: AssetSymbol | None = None


class TechnicalAnalysisResult(BaseModel):
    symbol: AssetSymbol
    timeframe: str
    generated_at: datetime
    trend: TrendDirection
    structure_events: list[StructureEvent]
    order_blocks: list[OrderBlock]
    fibonacci: FibonacciLevels | None
    indicators: IndicatorSnapshot
    candlestick_patterns: list[CandlestickPattern] = []
    current_price: float


class TradeAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    HOLD = "HOLD"


class TradeDecision(BaseModel):
    symbol: AssetSymbol
    action: TradeAction
    confidence: float = Field(ge=0.0, le=1.0)
    risk_reward_ratio: float | None = None
    entry_zone: tuple[float, float] | None = None
    stop_loss: float | None = None
    take_profit: list[float] = []
    invalidation_level: float | None = None
    reasoning: str
    generated_at: datetime


class AssetComparison(BaseModel):
    """The head-to-head Gold vs BTC verdict the AI layer produces."""
    gold: TradeDecision
    btc: TradeDecision
    preferred_asset: AssetSymbol
    comparison_reasoning: str
    generated_at: datetime
