"""
Fibonacci retracement engine: finds the dominant recent swing high/low pair
and computes standard retracement levels against it.

Swing detection uses a simple fractal method (a candle is a swing high if
its high is the max within `order` candles on each side; swing low mirrors
this on lows). This is intentionally simple and explainable rather than a
black-box peak-finder — traders reviewing signals can verify it by eye.

Anchor selection: among all swing highs/lows found in the lookback window,
we anchor the fib to the swing HIGH with the highest price and the swing
LOW with the lowest price — i.e. the two points that span the largest
move — rather than simply the chronologically most-recent swing of each
type. Picking the latest swing high and latest swing low independently can
pair two points that are only a few candles apart during a small
consolidation, producing a fib squeezed into a tiny price band that
ignores the actual dominant leg on the chart. Anchoring to the extremes
keeps the fib aligned with the swing a trader would draw by eye.
"""
import pandas as pd

from app.models.schemas import Candle, FibonacciLevels, TrendDirection
from app.strategies.indicators import candles_to_df

_FIB_RATIOS = [0.236, 0.382, 0.5, 0.618, 0.786]


def find_fibonacci_levels(candles: list[Candle], order: int = 3, lookback: int = 60) -> FibonacciLevels | None:
    df = candles_to_df(candles).tail(lookback).reset_index(drop=True)
    if len(df) < order * 2 + 2:
        return None

    swing_highs = _find_swings(df["high"], order, find_max=True)
    swing_lows = _find_swings(df["low"], order, find_max=False)

    if not swing_highs or not swing_lows:
        return None

    # Anchor to the most extreme swing high and swing low in the window —
    # the pair that spans the dominant move — not just the latest of each.
    high_idx, swing_high = max(swing_highs, key=lambda s: s[1])
    low_idx, swing_low = min(swing_lows, key=lambda s: s[1])

    diff = swing_high - swing_low
    if diff <= 0:
        return None

    # Direction of the impulse: whichever extreme came LAST chronologically
    # determines whether we're retracing a bullish or bearish leg.
    direction = TrendDirection.BULLISH if high_idx > low_idx else TrendDirection.BEARISH

    levels = {}
    for ratio in _FIB_RATIOS:
        if direction == TrendDirection.BULLISH:
            # retracement measured down from the high
            levels[str(ratio)] = round(swing_high - diff * ratio, 4)
        else:
            # retracement measured up from the low
            levels[str(ratio)] = round(swing_low + diff * ratio, 4)

    return FibonacciLevels(
        swing_high=round(swing_high, 4),
        swing_low=round(swing_low, 4),
        direction=direction,
        levels=levels,
    )


def _find_swings(series: pd.Series, order: int, find_max: bool) -> list[tuple[int, float]]:
    swings = []
    for i in range(order, len(series) - order):
        window = series[i - order: i + order + 1]
        if find_max and series[i] == window.max():
            swings.append((i, float(series[i])))
        elif not find_max and series[i] == window.min():
            swings.append((i, float(series[i])))
    return swings
