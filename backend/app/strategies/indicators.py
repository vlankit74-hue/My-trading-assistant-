"""
Classic indicator layer: RSI (+ divergence detection), MACD (+ crossover
detection), EMA 20/50/200 (+ trend classification).

Computed with plain pandas math instead of pandas-ta. Reason: pandas-ta is
unmaintained and its squeeze_pro.py imports `np.NaN` at package-load time,
which crashes on numpy>=2.0 (np.NaN was removed in NumPy 2.0) — an easy way
to break a fresh `pip install` on a host you don't control (like Render).
RSI/MACD/EMA are simple enough to hand-roll with zero extra dependencies
and zero version-pinning risk.
"""
import pandas as pd

from app.models.schemas import Candle, IndicatorSnapshot, TrendDirection


def candles_to_df(candles: list[Candle]) -> pd.DataFrame:
    df = pd.DataFrame([c.model_dump() for c in candles])
    df = df.sort_values("timestamp").reset_index(drop=True)
    return df


def _ema(series: pd.Series, length: int) -> pd.Series:
    return series.ewm(span=length, adjust=False).mean()


def _rsi(series: pd.Series, length: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    # Wilder's smoothing (equivalent to the classic RSI definition)
    avg_gain = gain.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / length, min_periods=length, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    rsi = rsi.where(avg_loss != 0, 100.0)  # if no losses at all, RSI = 100
    return rsi


def _macd(series: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = _ema(series, fast)
    ema_slow = _ema(series, slow)
    macd_line = ema_fast - ema_slow
    signal_line = _ema(macd_line, signal)
    return pd.DataFrame({"macd": macd_line, "macd_signal": signal_line})


def compute_indicators(candles: list[Candle]) -> IndicatorSnapshot:
    df = candles_to_df(candles)
    if len(df) < 200:
        # Not enough history for EMA200; return what we can.
        return _compute_partial(df)

    df["rsi_14"] = _rsi(df["close"], length=14)
    macd_df = _macd(df["close"], fast=12, slow=26, signal=9)
    df["macd"] = macd_df["macd"]
    df["macd_signal"] = macd_df["macd_signal"]
    df["ema_20"] = _ema(df["close"], length=20)
    df["ema_50"] = _ema(df["close"], length=50)
    df["ema_200"] = _ema(df["close"], length=200)

    last = df.iloc[-1]
    prev = df.iloc[-2]

    macd_crossover = _detect_macd_crossover(prev, last)
    rsi_divergence = _detect_rsi_divergence(df)
    ema_trend = _classify_ema_trend(last)

    return IndicatorSnapshot(
        rsi_14=round(float(last["rsi_14"]), 2) if pd.notna(last["rsi_14"]) else None,
        rsi_divergence=rsi_divergence,
        macd=round(float(last["macd"]), 4) if pd.notna(last["macd"]) else None,
        macd_signal=round(float(last["macd_signal"]), 4) if pd.notna(last["macd_signal"]) else None,
        macd_crossover=macd_crossover,
        ema_20=round(float(last["ema_20"]), 2) if pd.notna(last["ema_20"]) else None,
        ema_50=round(float(last["ema_50"]), 2) if pd.notna(last["ema_50"]) else None,
        ema_200=round(float(last["ema_200"]), 2) if pd.notna(last["ema_200"]) else None,
        ema_trend=ema_trend,
    )


def _compute_partial(df: pd.DataFrame) -> IndicatorSnapshot:
    """Best-effort indicator snapshot when there isn't enough history for EMA200."""
    if len(df) < 26:
        return IndicatorSnapshot()
    df["rsi_14"] = _rsi(df["close"], length=14)
    ema_20 = _ema(df["close"], length=20) if len(df) >= 20 else None
    last = df.iloc[-1]
    return IndicatorSnapshot(
        rsi_14=round(float(last["rsi_14"]), 2) if pd.notna(last["rsi_14"]) else None,
        ema_20=round(float(ema_20.iloc[-1]), 2) if ema_20 is not None and pd.notna(ema_20.iloc[-1]) else None,
    )


def _detect_macd_crossover(prev: pd.Series, last: pd.Series) -> str | None:
    if pd.isna(prev["macd"]) or pd.isna(prev["macd_signal"]):
        return None
    prev_diff = prev["macd"] - prev["macd_signal"]
    curr_diff = last["macd"] - last["macd_signal"]
    if prev_diff <= 0 < curr_diff:
        return "bullish_cross"
    if prev_diff >= 0 > curr_diff:
        return "bearish_cross"
    return None


def _detect_rsi_divergence(df: pd.DataFrame, lookback: int = 20) -> str | None:
    """
    Simplified swing-based divergence: compares the two most recent local
    price extremes in the lookback window against RSI at those same points.
    Regular bullish divergence: price makes a lower low, RSI makes a higher low.
    Regular bearish divergence: price makes a higher high, RSI makes a lower high.
    """
    window = df.tail(lookback).reset_index(drop=True)
    if len(window) < 5 or window["rsi_14"].isna().any():
        return None

    lows_idx = _local_extrema_indices(window["low"], find_min=True)
    highs_idx = _local_extrema_indices(window["high"], find_min=False)

    if len(lows_idx) >= 2:
        i1, i2 = lows_idx[-2], lows_idx[-1]
        if window["low"][i2] < window["low"][i1] and window["rsi_14"][i2] > window["rsi_14"][i1]:
            return "bullish_divergence"

    if len(highs_idx) >= 2:
        i1, i2 = highs_idx[-2], highs_idx[-1]
        if window["high"][i2] > window["high"][i1] and window["rsi_14"][i2] < window["rsi_14"][i1]:
            return "bearish_divergence"

    return None


def _local_extrema_indices(series: pd.Series, find_min: bool, order: int = 2) -> list[int]:
    indices = []
    for i in range(order, len(series) - order):
        window = series[i - order: i + order + 1]
        if find_min and series[i] == window.min():
            indices.append(i)
        elif not find_min and series[i] == window.max():
            indices.append(i)
    return indices


def _classify_ema_trend(last: pd.Series) -> TrendDirection | None:
    if pd.isna(last.get("ema_20")) or pd.isna(last.get("ema_50")) or pd.isna(last.get("ema_200")):
        return None
    if last["ema_20"] > last["ema_50"] > last["ema_200"]:
        return TrendDirection.BULLISH
    if last["ema_20"] < last["ema_50"] < last["ema_200"]:
        return TrendDirection.BEARISH
    return TrendDirection.NEUTRAL
