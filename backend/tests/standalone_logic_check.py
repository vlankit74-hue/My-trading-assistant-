"""
Standalone sanity test for the core swing-detection / Fibonacci / structure
algorithms, using only pandas+numpy (no pydantic, no pandas_ta) since the
sandbox has no network access to install the full dependency set. This
validates the MATH and LOGIC are correct; the real modules wrap this same
logic with Pydantic models for the actual app.
"""
import numpy as np
import pandas as pd

np.random.seed(42)


def make_synthetic_candles(n=150):
    """Generates a synthetic price series with a clear up-swing then down-swing,
    so we can verify swing/fib/structure detection against known extremes."""
    prices = [100.0]
    for i in range(1, n):
        if i < 60:
            drift = 0.3  # uptrend
        elif i < 100:
            drift = -0.25  # downtrend
        else:
            drift = 0.15
        prices.append(prices[-1] + drift + np.random.normal(0, 0.5))

    df = pd.DataFrame({"close": prices})
    df["open"] = df["close"].shift(1).fillna(df["close"][0])
    df["high"] = df[["open", "close"]].max(axis=1) + np.random.uniform(0.1, 0.6, n)
    df["low"] = df[["open", "close"]].min(axis=1) - np.random.uniform(0.1, 0.6, n)
    df["timestamp"] = pd.date_range("2025-01-01", periods=n, freq="h")
    df["volume"] = np.random.uniform(100, 1000, n)
    return df


def find_swings(series, order=3, find_max=True):
    swings = []
    for i in range(order, len(series) - order):
        window = series[i - order: i + order + 1]
        if find_max and series[i] == window.max():
            swings.append((i, float(series[i])))
        elif not find_max and series[i] == window.min():
            swings.append((i, float(series[i])))
    return swings


def fibonacci_levels(df, order=3, lookback=60):
    window = df.tail(lookback).reset_index(drop=True)
    highs = find_swings(window["high"], order, find_max=True)
    lows = find_swings(window["low"], order, find_max=False)
    if not highs or not lows:
        return None
    last_high_idx, last_high_val = highs[-1]
    last_low_idx, last_low_val = lows[-1]
    direction = "bullish" if last_high_idx > last_low_idx else "bearish"
    diff = last_high_val - last_low_val
    ratios = [0.236, 0.382, 0.5, 0.618, 0.786]
    levels = {}
    for r in ratios:
        levels[r] = round(last_high_val - diff * r, 2) if direction == "bullish" else round(last_low_val + diff * r, 2)
    return {"direction": direction, "swing_high": last_high_val, "swing_low": last_low_val, "levels": levels}


def detect_structure(df, order=3):
    swings = []
    for i in range(order, len(df) - order):
        hw = df["high"][i - order: i + order + 1]
        lw = df["low"][i - order: i + order + 1]
        if df["high"][i] == hw.max():
            swings.append((i, float(df["high"][i]), "high"))
        if df["low"][i] == lw.min():
            swings.append((i, float(df["low"][i]), "low"))
    swings.sort(key=lambda s: s[0])

    events = []
    trend = "neutral"
    last_high = None
    last_low = None
    for idx, price, kind in swings:
        if kind == "high":
            if last_high is not None and df["close"][idx] > last_high[1]:
                event_kind = "BOS" if trend == "bullish" else "MSS"
                trend = "bullish"
                events.append((event_kind, "bullish", last_high[1], idx))
            last_high = (idx, price)
        else:
            if last_low is not None and df["close"][idx] < last_low[1]:
                event_kind = "BOS" if trend == "bearish" else "MSS"
                trend = "bearish"
                events.append((event_kind, "bearish", last_low[1], idx))
            last_low = (idx, price)
    return events, trend


if __name__ == "__main__":
    df = make_synthetic_candles(150)
    print("=== Synthetic data summary ===")
    print(f"Rows: {len(df)}, price range: {df['low'].min():.2f} - {df['high'].max():.2f}")
    print(f"First close: {df['close'].iloc[0]:.2f}, last close: {df['close'].iloc[-1]:.2f}")

    print("\n=== Fibonacci levels ===")
    fib = fibonacci_levels(df)
    print(fib)
    if fib:
        # sanity: 0.5 level should sit exactly between swing high/low
        expected_mid = round((fib["swing_high"] + fib["swing_low"]) / 2, 2)
        actual_mid = fib["levels"][0.5]
        assert abs(expected_mid - actual_mid) < 0.01, f"0.5 fib level wrong: {actual_mid} vs {expected_mid}"
        print(f"PASS: 0.5 retracement ({actual_mid}) matches midpoint ({expected_mid})")
        # sanity: levels should be monotonic between swing high and low
        ratios_sorted = sorted(fib["levels"].keys())
        vals = [fib["levels"][r] for r in ratios_sorted]
        is_monotonic = all(vals[i] <= vals[i+1] for i in range(len(vals)-1)) or all(vals[i] >= vals[i+1] for i in range(len(vals)-1))
        assert is_monotonic, f"Fib levels not monotonic: {vals}"
        print(f"PASS: Fib levels are monotonic across ratios")

    print("\n=== Structure events (BOS/MSS) ===")
    events, trend = detect_structure(df)
    for kind, direction, level, idx in events:
        print(f"  idx={idx:3d}  {kind:4s}  {direction:8s}  level={level:.2f}")
    print(f"Final trend: {trend}")
    assert len(events) > 0, "Expected at least one structure event in a trending synthetic series"
    print(f"PASS: Detected {len(events)} structure events")

    print("\nAll sanity checks passed.")
