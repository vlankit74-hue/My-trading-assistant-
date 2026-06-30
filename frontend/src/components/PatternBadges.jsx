import clsx from "clsx";

const PATTERN_LABELS = {
  bullish_engulfing: "Bullish Engulfing",
  bearish_engulfing: "Bearish Engulfing",
  hammer: "Hammer",
  shooting_star: "Shooting Star",
  bullish_pin_bar: "Bullish Pin Bar",
  bearish_pin_bar: "Bearish Pin Bar",
  doji: "Doji",
  morning_star: "Morning Star",
  evening_star: "Evening Star",
};

/**
 * Shows recently-detected candlestick price-action patterns as small
 * badges, color-coded by the bias they imply. Sits just under the
 * indicator strip so the AI's price-action read is visible at a glance,
 * not buried only in the signal card's text reasoning.
 */
export default function PatternBadges({ patterns }) {
  if (!patterns?.length) return null;

  // Show most recent first, de-duplicated by name (keep the latest of each)
  const seen = new Set();
  const recent = [...patterns].reverse().filter((p) => {
    if (seen.has(p.name)) return false;
    seen.add(p.name);
    return true;
  });

  return (
    <div className="flex flex-wrap gap-2 px-4 py-2 bg-panel-raised border-b border-hairline">
      <span className="text-[10px] text-text-faint uppercase tracking-wider self-center">
        Price Action
      </span>
      {recent.map((p, i) => (
        <span
          key={`${p.name}-${i}`}
          className={clsx(
            "text-[11px] px-2 py-0.5 rounded-sm font-medium",
            p.direction === "bullish" && "text-bull bg-bull-dim",
            p.direction === "bearish" && "text-bear bg-bear-dim",
            p.direction === "neutral" && "text-text-dim bg-hairline"
          )}
          title={`Detected at ${new Date(p.timestamp).toLocaleString()} · strength ${Math.round(p.strength * 100)}%`}
        >
          {PATTERN_LABELS[p.name] || p.name}
        </span>
      ))}
    </div>
  );
}
