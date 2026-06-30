import clsx from "clsx";

const ACTION_STYLES = {
  BUY: { text: "text-bull", bg: "bg-bull-dim", bar: "bg-bull", label: "BUY" },
  SELL: { text: "text-bear", bg: "bg-bear-dim", bar: "bg-bear", label: "SELL" },
  HOLD: { text: "text-signal", bg: "bg-signal-dim", bar: "bg-signal", label: "HOLD" },
};

function formatPrice(value, symbol) {
  if (value == null) return "—";
  const decimals = symbol === "BTCUSD" ? 0 : 2;
  return value.toLocaleString(undefined, { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}

export default function SignalCard({ symbol, label, decision, livePrice, loading }) {
  if (loading || !decision) {
    return (
      <div className="bg-panel border border-hairline rounded-sm p-4 animate-pulse">
        <div className="h-4 w-24 bg-hairline rounded mb-3" />
        <div className="h-8 w-32 bg-hairline rounded mb-2" />
        <div className="h-3 w-full bg-hairline rounded" />
      </div>
    );
  }

  const style = ACTION_STYLES[decision.action] || ACTION_STYLES.HOLD;
  const confidencePct = Math.round((decision.confidence || 0) * 100);

  return (
    <div className="bg-panel border border-hairline rounded-sm p-4 flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-text-dim uppercase tracking-wider">{label}</div>
          <div className="font-mono text-lg text-text-primary tabular-nums">
            {formatPrice(livePrice ?? decision.entry_zone?.[0], symbol)}
          </div>
        </div>
        <span
          className={clsx(
            "px-3 py-1 rounded-sm text-sm font-semibold tracking-wide",
            style.text,
            style.bg
          )}
        >
          {style.label}
        </span>
      </div>

      {/* Confidence meter — signature element: fills/recolors with live AI confidence */}
      <div>
        <div className="flex justify-between text-xs text-text-dim mb-1">
          <span>Confidence</span>
          <span className="font-mono">{confidencePct}%</span>
        </div>
        <div className="h-1.5 w-full bg-hairline rounded-full overflow-hidden">
          <div
            className={clsx("h-full rounded-full transition-all duration-700", style.bar)}
            style={{ width: `${confidencePct}%` }}
          />
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 text-xs">
        <div>
          <div className="text-text-faint uppercase tracking-wide">R:R</div>
          <div className="font-mono text-text-primary">
            {decision.risk_reward_ratio ? `1:${decision.risk_reward_ratio}` : "—"}
          </div>
        </div>
        <div>
          <div className="text-text-faint uppercase tracking-wide">Invalidation</div>
          <div className="font-mono text-text-primary">
            {formatPrice(decision.invalidation_level, symbol)}
          </div>
        </div>
        <div>
          <div className="text-text-faint uppercase tracking-wide">Stop Loss</div>
          <div className="font-mono text-text-primary">{formatPrice(decision.stop_loss, symbol)}</div>
        </div>
        <div>
          <div className="text-text-faint uppercase tracking-wide">Take Profit</div>
          <div className="font-mono text-text-primary">
            {decision.take_profit?.length ? formatPrice(decision.take_profit[0], symbol) : "—"}
          </div>
        </div>
      </div>

      <p className="text-xs text-text-dim leading-relaxed border-t border-hairline pt-2">
        {decision.reasoning}
      </p>
    </div>
  );
}
