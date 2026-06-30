"""
Candlestick price-action pattern recognition.

Detects a focused set of well-established reversal/continuation patterns
using precise geometric rules on candle bodies/wicks, rather than a
black-box classifier — so every detection can be verified by eye against
the chart, same philosophy as the SMC and Fibonacci modules.

Patterns covered:
- Bullish / Bearish Engulfing (2-candle reversal)
- Hammer / Shooting Star (1-candle reversal, long wick rejection)
- Doji (1-candle indecision)
- Morning Star / Evening Star (3-candle reversal)
- Bullish / Bearish Pin Bar (1-candle rejection, similar to hammer/shooting
  star but evaluated independent of prior trend direction)

Only the most recent `lookback` candles are scanned, and only patterns
completing in the last few candles are returned — older patterns have
already played out and aren't actionable for a live signal.
"""
import pandas as pd

from app.models.schemas import Candle, CandlestickPattern, TrendDirection
from app.strategies.indicators import candles_to_df

_RECENT_WINDOW = 5  # only report patterns completing within the last N candles


def _body(row: pd.Series) -> float:
    return abs(row["close"] - row["open"])


def _range(row: pd.Series) -> float:
    return row["high"] - row["low"]


def _upper_wick(row: pd.Series) -> float:
    return row["high"] - max(row["open"], row["close"])


def _lower_wick(row: pd.Series) -> float:
    return min(row["open"], row["close"]) - row["low"]


def _is_bullish(row: pd.Series) -> bool:
    return row["close"] > row["open"]


def _is_bearish(row: pd.Series) -> bool:
    return row["close"] < row["open"]


def detect_candlestick_patterns(candles: list[Candle], lookback: int = 60) -> list[CandlestickPattern]:
    df = candles_to_df(candles).tail(lookback).reset_index(drop=True)
    if len(df) < 3:
        return []

    patterns: list[CandlestickPattern] = []
    start = max(2, len(df) - _RECENT_WINDOW)

    for i in range(start, len(df)):
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        prev2 = df.iloc[i - 2] if i >= 2 else None

        rng = _range(row)
        if rng <= 0:
            continue

        # --- Engulfing (2-candle) ---
        if _is_bullish(row) and _is_bearish(prev):
            if row["close"] >= prev["open"] and row["open"] <= prev["close"]:
                body_ratio = _body(row) / max(_body(prev), 1e-9)
                patterns.append(CandlestickPattern(
                    name="bullish_engulfing", direction=TrendDirection.BULLISH,
                    timestamp=row["timestamp"], strength=min(1.0, 0.5 + 0.1 * body_ratio),
                ))
        if _is_bearish(row) and _is_bullish(prev):
            if row["close"] <= prev["open"] and row["open"] >= prev["close"]:
                body_ratio = _body(row) / max(_body(prev), 1e-9)
                patterns.append(CandlestickPattern(
                    name="bearish_engulfing", direction=TrendDirection.BEARISH,
                    timestamp=row["timestamp"], strength=min(1.0, 0.5 + 0.1 * body_ratio),
                ))

        # --- Hammer / Shooting Star (long single wick rejection) ---
        # Thresholds are relative to the candle's total RANGE, not its body
        # — a body-relative ceiling on the opposite wick breaks down when
        # the body is tiny (any wick at all then "exceeds" half the body).
        body = _body(row)
        lower_wick = _lower_wick(row)
        upper_wick = _upper_wick(row)

        if lower_wick >= rng * 0.55 and upper_wick <= rng * 0.15 and body <= rng * 0.4:
            # Long lower wick = rejection of lower prices. More meaningful
            # after a downtrend (hammer) than in isolation.
            prior_trend_down = prev["close"] < df.iloc[max(0, i - 3)]["close"]
            patterns.append(CandlestickPattern(
                name="hammer" if prior_trend_down else "bullish_pin_bar",
                direction=TrendDirection.BULLISH,
                timestamp=row["timestamp"],
                strength=min(1.0, 0.5 + 0.5 * (lower_wick / rng)),
            ))

        if upper_wick >= rng * 0.55 and lower_wick <= rng * 0.15 and body <= rng * 0.4:
            prior_trend_up = prev["close"] > df.iloc[max(0, i - 3)]["close"]
            patterns.append(CandlestickPattern(
                name="shooting_star" if prior_trend_up else "bearish_pin_bar",
                direction=TrendDirection.BEARISH,
                timestamp=row["timestamp"],
                strength=min(1.0, 0.5 + 0.5 * (upper_wick / rng)),
            ))

        # --- Doji (indecision: tiny body, AND wicks roughly balanced on
        # both sides — a tiny body with a heavily one-sided wick is a
        # hammer/shooting star, not a doji, even though both have small
        # bodies relative to range). ---
        if body <= rng * 0.1 and min(upper_wick, lower_wick) >= rng * 0.15:
            patterns.append(CandlestickPattern(
                name="doji", direction=TrendDirection.NEUTRAL,
                timestamp=row["timestamp"], strength=0.4,
            ))

        # --- Morning Star / Evening Star (3-candle reversal) ---
        if prev2 is not None:
            prev2_body = _body(prev2)
            prev_body = _body(prev)
            curr_body = _body(row)

            # Morning star: big bearish candle, small-body indecisive middle
            # candle (gapping down), then big bullish candle closing back
            # into the first candle's body.
            if (
                _is_bearish(prev2) and prev2_body > 0
                and prev_body < prev2_body * 0.5
                and _is_bullish(row) and curr_body > prev2_body * 0.5
                and row["close"] > (prev2["open"] + prev2["close"]) / 2
            ):
                patterns.append(CandlestickPattern(
                    name="morning_star", direction=TrendDirection.BULLISH,
                    timestamp=row["timestamp"], strength=0.75,
                ))

            # Evening star: mirror image, bullish -> small body -> bearish.
            if (
                _is_bullish(prev2) and prev2_body > 0
                and prev_body < prev2_body * 0.5
                and _is_bearish(row) and curr_body > prev2_body * 0.5
                and row["close"] < (prev2["open"] + prev2["close"]) / 2
            ):
                patterns.append(CandlestickPattern(
                    name="evening_star", direction=TrendDirection.BEARISH,
                    timestamp=row["timestamp"], strength=0.75,
                ))

    return patterns
