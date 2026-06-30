import clsx from "clsx";

export default function AssetComparePanel({ comparison, loading }) {
  if (loading || !comparison) {
    return (
      <div className="bg-panel border border-hairline rounded-sm p-4 animate-pulse h-32" />
    );
  }

  const preferredLabel = comparison.preferred_asset === "XAUUSD" ? "Gold" : "Bitcoin";

  return (
    <div className="bg-panel-raised border border-hairline rounded-sm p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-xs text-text-dim uppercase tracking-wider">Head-to-Head</span>
        <span className="text-xs font-mono text-text-faint">
          {new Date(comparison.generated_at).toLocaleTimeString()}
        </span>
      </div>
      <div className="flex items-baseline gap-2 mb-3">
        <span className="text-text-dim text-sm">Better setup right now:</span>
        <span
          className={clsx(
            "font-semibold text-base",
            comparison.preferred_asset === "XAUUSD" ? "text-signal" : "text-bull"
          )}
        >
          {preferredLabel}
        </span>
      </div>
      <p className="text-xs text-text-dim leading-relaxed">{comparison.comparison_reasoning}</p>
    </div>
  );
}
