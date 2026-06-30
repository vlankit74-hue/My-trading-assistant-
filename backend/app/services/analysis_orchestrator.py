"""
Combines indicators + Fibonacci + SMC + candlestick price-action patterns
into a single TechnicalAnalysisResult. This is the one function the API
layer and AI decision layer call — they never touch the individual
strategy modules directly.
"""
from datetime import datetime, timezone

from app.models.schemas import AssetSymbol, Candle, TechnicalAnalysisResult
from app.strategies.candlestick_patterns import detect_candlestick_patterns
from app.strategies.fibonacci import find_fibonacci_levels
from app.strategies.indicators import compute_indicators
from app.strategies.smart_money_concepts import detect_order_blocks, detect_structure


def run_technical_analysis(
    symbol: AssetSymbol, timeframe: str, candles: list[Candle]
) -> TechnicalAnalysisResult:
    if not candles:
        raise ValueError(f"No candles supplied for {symbol}/{timeframe}")

    structure_events, trend = detect_structure(candles)
    order_blocks = detect_order_blocks(candles, structure_events)
    fib = find_fibonacci_levels(candles)
    indicators = compute_indicators(candles)
    candlestick_patterns = detect_candlestick_patterns(candles)

    return TechnicalAnalysisResult(
        symbol=symbol,
        timeframe=timeframe,
        generated_at=datetime.now(timezone.utc),
        trend=trend,
        structure_events=structure_events,
        order_blocks=order_blocks,
        fibonacci=fib,
        indicators=indicators,
        candlestick_patterns=candlestick_patterns,
        current_price=candles[-1].close,
    )
