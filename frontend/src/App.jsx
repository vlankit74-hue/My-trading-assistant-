import { useState } from "react";
import clsx from "clsx";
import PriceChart from "./components/PriceChart";
import SignalCard from "./components/SignalCard";
import AssetComparePanel from "./components/AssetComparePanel";
import NewsFeed from "./components/NewsFeed";
import IndicatorStrip from "./components/IndicatorStrip";
import PatternBadges from "./components/PatternBadges";
import { useCandles, useAnalysis, useNews, useSignalCompare } from "./hooks/useMarketData";
import { useLivePrice } from "./hooks/useLivePrice";

const TIMEFRAMES = ["M15", "H1", "H4", "D1"];
const ASSETS = [
  { symbol: "XAUUSD", label: "Gold · XAU/USD" },
  { symbol: "BTCUSD", label: "Bitcoin · BTC/USD" },
];

export default function App() {
  const [activeSymbol, setActiveSymbol] = useState("XAUUSD");
  const [timeframe, setTimeframe] = useState("H1");

  const { data: candleSeries, isLoading: candlesLoading } = useCandles(activeSymbol, timeframe);
  const { data: analysis, isLoading: analysisLoading } = useAnalysis(activeSymbol, timeframe);
  const { data: news, isLoading: newsLoading } = useNews(activeSymbol);
  const { data: comparison, isLoading: compareLoading } = useSignalCompare(timeframe);
  const { price: livePrice, connected: liveConnected } = useLivePrice(activeSymbol);

  const activeDecision = comparison
    ? activeSymbol === "XAUUSD"
      ? comparison.gold
      : comparison.btc
    : null;

  return (
    <div className="min-h-screen bg-base text-text-primary">
      {/* Header */}
      <header className="border-b border-hairline px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="text-sm font-semibold tracking-wide">AI TRADING ASSISTANT</span>
          <span className="text-xs text-text-faint font-mono">GOLD · BITCOIN</span>
          <span className="flex items-center gap-1.5 text-[10px] font-mono text-text-faint">
            <span
              className={clsx(
                "w-1.5 h-1.5 rounded-full",
                liveConnected ? "bg-bull" : "bg-text-faint"
              )}
            />
            {liveConnected ? "LIVE" : "CONNECTING…"}
          </span>
        </div>
        <div className="flex gap-1">
          {TIMEFRAMES.map((tf) => (
            <button
              key={tf}
              onClick={() => setTimeframe(tf)}
              className={clsx(
                "px-2.5 py-1 text-xs font-mono rounded-sm transition-colors",
                timeframe === tf
                  ? "bg-bull-dim text-bull"
                  : "text-text-dim hover:text-text-primary hover:bg-panel-raised"
              )}
            >
              {tf}
            </button>
          ))}
        </div>
      </header>

      {/* Asset tabs */}
      <div className="flex gap-1 px-6 pt-4">
        {ASSETS.map((asset) => (
          <button
            key={asset.symbol}
            onClick={() => setActiveSymbol(asset.symbol)}
            className={clsx(
              "px-4 py-2 text-sm rounded-sm border transition-colors",
              activeSymbol === asset.symbol
                ? "border-bull text-bull bg-bull-dim"
                : "border-hairline text-text-dim hover:text-text-primary"
            )}
          >
            {asset.label}
          </button>
        ))}
      </div>

      {/* Main grid */}
      <main className="grid grid-cols-1 lg:grid-cols-[1fr_360px] gap-4 p-6">
        {/* Chart column */}
        <section className="flex flex-col">
          <div className="bg-panel border border-hairline rounded-sm overflow-hidden">
            <IndicatorStrip indicators={analysis?.indicators} />
            <PatternBadges patterns={analysis?.candlestick_patterns} />
            {candlesLoading ? (
              <div className="h-[460px] flex items-center justify-center text-text-dim text-sm">
                Loading chart…
              </div>
            ) : (
              <PriceChart
                candles={candleSeries?.candles}
                fibonacci={analysis?.fibonacci}
                orderBlocks={analysis?.order_blocks}
                livePrice={livePrice}
              />
            )}
          </div>

          <div className="mt-4">
            <h2 className="text-xs text-text-dim uppercase tracking-wider mb-2">Latest Headlines</h2>
            <NewsFeed news={news} loading={newsLoading} />
          </div>
        </section>

        {/* Signal rail */}
        <section className="flex flex-col gap-4">
          <h2 className="text-xs text-text-dim uppercase tracking-wider">AI Signal</h2>
          <SignalCard
            symbol={activeSymbol}
            label={activeSymbol === "XAUUSD" ? "Gold · XAU/USD" : "Bitcoin · BTC/USD"}
            decision={activeDecision}
            livePrice={livePrice}
            loading={compareLoading || analysisLoading}
          />

          <h2 className="text-xs text-text-dim uppercase tracking-wider mt-2">Gold vs Bitcoin</h2>
          <AssetComparePanel comparison={comparison} loading={compareLoading} />

          <div className="text-[11px] text-text-faint leading-relaxed border-t border-hairline pt-3 mt-2">
            This dashboard produces automated technical and sentiment analysis, not investment
            advice. Markets are risky — SMC, Fibonacci, and indicator setups do not guarantee
            future outcomes.
          </div>
        </section>
      </main>
    </div>
  );
}
