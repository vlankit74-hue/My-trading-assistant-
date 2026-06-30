import clsx from "clsx";

export default function IndicatorStrip({ indicators }) {
  if (!indicators) return null;

  const rsiColor = indicators.rsi_14 > 70 ? "text-bear" : indicators.rsi_14 < 30 ? "text-bull" : "text-text-primary";

  return (
    <div className="flex flex-wrap gap-4 text-xs font-mono px-4 py-2 bg-panel-raised border-y border-hairline">
      <div className="flex gap-1.5 items-baseline">
        <span className="text-text-faint uppercase">RSI</span>
        <span className={rsiColor}>{indicators.rsi_14?.toFixed(1) ?? "—"}</span>
        {indicators.rsi_divergence && (
          <span className="text-signal text-[10px]">
            {indicators.rsi_divergence === "bullish_divergence" ? "↗ DIV" : "↘ DIV"}
          </span>
        )}
      </div>
      <div className="flex gap-1.5 items-baseline">
        <span className="text-text-faint uppercase">MACD</span>
        <span className="text-text-primary">{indicators.macd?.toFixed(3) ?? "—"}</span>
        {indicators.macd_crossover && (
          <span className={indicators.macd_crossover === "bullish_cross" ? "text-bull" : "text-bear"}>
            {indicators.macd_crossover === "bullish_cross" ? "↑ CROSS" : "↓ CROSS"}
          </span>
        )}
      </div>
      <div className="flex gap-1.5 items-baseline">
        <span className="text-text-faint uppercase">EMA 20/50/200</span>
        <span className="text-text-primary">
          {indicators.ema_20?.toFixed(1) ?? "—"} / {indicators.ema_50?.toFixed(1) ?? "—"} /{" "}
          {indicators.ema_200?.toFixed(1) ?? "—"}
        </span>
        {indicators.ema_trend && (
          <span
            className={clsx(
              indicators.ema_trend === "bullish" && "text-bull",
              indicators.ema_trend === "bearish" && "text-bear",
              indicators.ema_trend === "neutral" && "text-text-dim"
            )}
          >
            {indicators.ema_trend.toUpperCase()}
          </span>
        )}
      </div>
    </div>
  );
}
