import { useEffect, useRef } from "react";
import { createChart, ColorType } from "lightweight-charts";

const FIB_COLORS = {
  "0.236": "#454B54",
  "0.382": "#6B7480",
  "0.5": "#E8A33D",
  "0.618": "#6B7480",
  "0.786": "#454B54",
};

/**
 * Renders OHLC candles with Fibonacci retracement lines and Order Block
 * zones overlaid. This chart IS the analysis surface — annotations are
 * drawn directly on price rather than buried in a side panel.
 *
 * `livePrice` (a single number from the WebSocket tick stream) updates
 * just the close/high/low of the CURRENT (most recent) bar in place via
 * series.update() — the lightweight-charts-native way to animate the
 * live-forming bar without waiting for the next REST refetch (which only
 * happens every 60s). Without this, the chart looked frozen between
 * refetches even though the backend was streaming ticks the whole time.
 */
export default function PriceChart({ candles, fibonacci, orderBlocks, livePrice, height = 460 }) {
  const containerRef = useRef(null);
  const chartRef = useRef(null);
  const seriesRef = useRef(null);
  const lastBarRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: {
        background: { type: ColorType.Solid, color: "#12161C" },
        textColor: "#6B7480",
        fontFamily: "JetBrains Mono, monospace",
        fontSize: 11,
      },
      grid: {
        vertLines: { color: "#1E242C" },
        horzLines: { color: "#1E242C" },
      },
      crosshair: { mode: 0 },
      rightPriceScale: { borderColor: "#1E242C" },
      timeScale: { borderColor: "#1E242C", timeVisible: true, secondsVisible: false },
    });

    const series = chart.addCandlestickSeries({
      upColor: "#3FBF7F",
      downColor: "#E5484D",
      borderUpColor: "#3FBF7F",
      borderDownColor: "#E5484D",
      wickUpColor: "#3FBF7F",
      wickDownColor: "#E5484D",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const handleResize = () => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    };
    window.addEventListener("resize", handleResize);
    handleResize();

    return () => {
      window.removeEventListener("resize", handleResize);
      chart.remove();
    };
  }, [height]);

  // Update candle data
  useEffect(() => {
    if (!seriesRef.current || !candles?.length) return;
    const formatted = candles.map((c) => ({
      time: Math.floor(new Date(c.timestamp).getTime() / 1000),
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    seriesRef.current.setData(formatted);
    chartRef.current?.timeScale().fitContent();
    lastBarRef.current = formatted[formatted.length - 1] || null;
  }, [candles]);

  // Animate the live-forming bar as WebSocket ticks arrive, without
  // waiting for the next 60s REST refetch.
  useEffect(() => {
    if (!seriesRef.current || !lastBarRef.current || livePrice == null) return;
    const updated = {
      ...lastBarRef.current,
      close: livePrice,
      high: Math.max(lastBarRef.current.high, livePrice),
      low: Math.min(lastBarRef.current.low, livePrice),
    };
    lastBarRef.current = updated;
    seriesRef.current.update(updated);
  }, [livePrice]);

  // Draw Fibonacci levels as price lines
  useEffect(() => {
    if (!seriesRef.current || !fibonacci?.levels) return;
    const priceLines = [];
    Object.entries(fibonacci.levels).forEach(([ratio, price]) => {
      const line = seriesRef.current.createPriceLine({
        price,
        color: FIB_COLORS[ratio] || "#6B7480",
        lineWidth: 1,
        lineStyle: 2,
        axisLabelVisible: true,
        title: `Fib ${ratio}`,
      });
      priceLines.push(line);
    });
    return () => priceLines.forEach((l) => seriesRef.current?.removePriceLine(l));
  }, [fibonacci]);

  // Draw Order Block zones as price lines (top + bottom of each OB range)
  useEffect(() => {
    if (!seriesRef.current || !orderBlocks?.length) return;
    const priceLines = [];
    orderBlocks.forEach((ob) => {
      const color = ob.type === "bullish" ? "#1F4D38" : "#4D2326";
      [ob.high, ob.low].forEach((price) => {
        const line = seriesRef.current.createPriceLine({
          price,
          color,
          lineWidth: 1,
          lineStyle: 0,
          axisLabelVisible: false,
        });
        priceLines.push(line);
      });
    });
    return () => priceLines.forEach((l) => seriesRef.current?.removePriceLine(l));
  }, [orderBlocks]);

  return <div ref={containerRef} className="w-full" />;
}
