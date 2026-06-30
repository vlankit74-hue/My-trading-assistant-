import clsx from "clsx";

function sentimentBadge(score) {
  if (score > 0.15) return { label: "Bullish", cls: "text-bull bg-bull-dim" };
  if (score < -0.15) return { label: "Bearish", cls: "text-bear bg-bear-dim" };
  return { label: "Neutral", cls: "text-text-dim bg-hairline" };
}

export default function NewsFeed({ news, loading }) {
  if (loading) {
    return <div className="bg-panel border border-hairline rounded-sm p-4 h-40 animate-pulse" />;
  }

  if (!news?.length) {
    return (
      <div className="bg-panel border border-hairline rounded-sm p-4 text-xs text-text-dim">
        No recent headlines.
      </div>
    );
  }

  return (
    <div className="bg-panel border border-hairline rounded-sm divide-y divide-hairline max-h-72 overflow-y-auto">
      {news.map((item, i) => {
        const badge = sentimentBadge(item.sentiment_score);
        return (
          <a
            key={i}
            href={item.url}
            target="_blank"
            rel="noopener noreferrer"
            className="flex items-start gap-3 p-3 hover:bg-panel-raised transition-colors"
          >
            <span className={clsx("shrink-0 text-[10px] px-1.5 py-0.5 rounded-sm font-medium mt-0.5", badge.cls)}>
              {badge.label}
            </span>
            <div className="min-w-0">
              <div className="text-sm text-text-primary leading-snug truncate">{item.title}</div>
              <div className="text-[11px] text-text-faint mt-0.5">
                {item.source} · {new Date(item.published_at).toLocaleTimeString()}
              </div>
            </div>
          </a>
        );
      })}
    </div>
  );
}
