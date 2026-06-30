"""
Smart Money Concepts (SMC) engine.

Core logic:
1. Track alternating swing highs/lows to build a structure map.
2. BOS (Break of Structure): price closes beyond the most recent swing
   high/low *in the direction of the prevailing trend* -> trend continuation.
3. MSS (Market Structure Shift): price closes beyond the most recent swing
   high/low *against* the prevailing trend -> potential reversal signal.
4. Order Block (OB): the last opposing candle immediately before the
   impulsive move that caused the BOS/MSS. E.g. for a bullish break, the OB
   is the last bearish candle before the up-move — smart money's footprint.

This is a simplified, rule-based implementation of concepts used by retail
SMC/ICT traders. It is deliberately conservative: it only tags well-formed
swings using the same fractal method as the Fibonacci module so structure
and fib levels stay consistent with each other.
"""
import pandas as pd

from app.models.schemas import Candle, OrderBlock, StructureEvent, TrendDirection
from app.strategies.indicators import candles_to_df

SwingPoint = tuple[int, float, str]  # (index, price, "high"|"low")


def _find_all_swings(df: pd.DataFrame, order: int = 3) -> list[SwingPoint]:
    swings: list[SwingPoint] = []
    for i in range(order, len(df) - order):
        high_window = df["high"][i - order: i + order + 1]
        low_window = df["low"][i - order: i + order + 1]
        if df["high"][i] == high_window.max():
            swings.append((i, float(df["high"][i]), "high"))
        if df["low"][i] == low_window.min():
            swings.append((i, float(df["low"][i]), "low"))
    swings.sort(key=lambda s: s[0])
    return swings


def detect_structure(candles: list[Candle], order: int = 3, lookback: int = 100) -> tuple[
    list[StructureEvent], TrendDirection
]:
    """
    Walks forward through swings, tracking the prevailing trend, and emits
    a BOS or MSS event each time price breaks the last relevant swing point.
    Returns (events, current_trend).
    """
    df = candles_to_df(candles).tail(lookback).reset_index(drop=True)
    if len(df) < order * 2 + 5:
        return [], TrendDirection.NEUTRAL

    swings = _find_all_swings(df, order)
    events: list[StructureEvent] = []
    trend = TrendDirection.NEUTRAL

    last_swing_high: SwingPoint | None = None
    last_swing_low: SwingPoint | None = None

    for idx, price, kind in swings:
        if kind == "high":
            if last_swing_high is not None:
                close_now = df["close"][idx]
                if close_now > last_swing_high[1]:
                    event_kind = "BOS" if trend == TrendDirection.BULLISH else "MSS"
                    trend = TrendDirection.BULLISH
                    events.append(StructureEvent(
                        kind=event_kind, direction=TrendDirection.BULLISH,
                        level=last_swing_high[1], timestamp=df["timestamp"][idx],
                    ))
            last_swing_high = (idx, price, kind)
        else:  # "low"
            if last_swing_low is not None:
                close_now = df["close"][idx]
                if close_now < last_swing_low[1]:
                    event_kind = "BOS" if trend == TrendDirection.BEARISH else "MSS"
                    trend = TrendDirection.BEARISH
                    events.append(StructureEvent(
                        kind=event_kind, direction=TrendDirection.BEARISH,
                        level=last_swing_low[1], timestamp=df["timestamp"][idx],
                    ))
            last_swing_low = (idx, price, kind)

    return events[-10:], trend  # cap to last 10 events to keep payloads small


def detect_order_blocks(candles: list[Candle], structure_events: list[StructureEvent],
                         lookback_candles: int = 100, max_blocks: int = 5) -> list[OrderBlock]:
    """
    For each structure event, walks backward from the break to find the
    last opposing candle before the impulsive move — that candle's
    high/low range is the Order Block.
    """
    df = candles_to_df(candles).tail(lookback_candles).reset_index(drop=True)
    if df.empty or not structure_events:
        return []

    order_blocks: list[OrderBlock] = []

    for event in structure_events:
        # locate the candle index matching this event's timestamp
        matches = df.index[df["timestamp"] == event.timestamp]
        if len(matches) == 0:
            continue
        break_idx = matches[0]

        opposing_is_bearish = event.direction == TrendDirection.BULLISH
        ob_idx = None
        for i in range(break_idx, max(break_idx - 15, -1), -1):
            is_bearish_candle = df["close"][i] < df["open"][i]
            is_bullish_candle = df["close"][i] > df["open"][i]
            if opposing_is_bearish and is_bearish_candle:
                ob_idx = i
                break
            if not opposing_is_bearish and is_bullish_candle:
                ob_idx = i
                break

        if ob_idx is None:
            continue

        candle_row = df.iloc[ob_idx]
        ob_type = TrendDirection.BULLISH if not opposing_is_bearish else TrendDirection.BEARISH
        order_blocks.append(OrderBlock(
            type=ob_type,
            high=round(float(candle_row["high"]), 4),
            low=round(float(candle_row["low"]), 4),
            timestamp=candle_row["timestamp"],
            mitigated=_is_mitigated(df, ob_idx, candle_row, ob_type),
        ))

    # de-duplicate near-identical blocks, keep most recent first
    order_blocks.sort(key=lambda ob: ob.timestamp, reverse=True)
    return order_blocks[:max_blocks]


def _is_mitigated(df: pd.DataFrame, ob_idx: int, candle_row: pd.Series, ob_type: TrendDirection) -> bool:
    """An OB is 'mitigated' if price has since traded back into its range."""
    later = df.iloc[ob_idx + 1:]
    if later.empty:
        return False
    if ob_type == TrendDirection.BULLISH:
        return bool((later["low"] <= candle_row["high"]).any())
    return bool((later["high"] >= candle_row["low"]).any())
