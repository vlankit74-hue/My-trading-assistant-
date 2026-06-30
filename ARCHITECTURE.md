# AI Trading Assistant — Architecture & Implementation Plan

## 1. System Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                            CLIENT (Browser)                          │
│   React Dashboard — Lightweight Charts, Signal Cards, News Feed       │
└───────────────────────────┬───────────────────────────────────────────┘
                            │ HTTPS (REST) + WSS (live prices/signals)
┌───────────────────────────▼───────────────────────────────────────────┐
│                         FASTAPI BACKEND (Python)                      │
│                                                                         │
│  ┌──────────────┐   ┌────────────────┐   ┌─────────────────────────┐ │
│  │   API Layer   │   │  WebSocket Hub │   │   Scheduler (APScheduler)│ │
│  │  /api/v1/*    │   │  /ws/prices    │   │  - pulls candles every  │ │
│  └──────┬───────┘   └───────┬────────┘   │    N seconds              │ │
│         │                   │             │  - recomputes signals    │ │
│  ┌──────▼───────────────────▼────────┐   │    every M minutes        │ │
│  │        Service Layer               │   └────────────┬─────────────┘ │
│  │  MarketDataService                  │                │               │
│  │  NewsService                        │◄───────────────┘               │
│  │  AnalysisOrchestrator               │                                │
│  └──────┬─────────────────┬───────────┘                                │
│         │                 │                                            │
│  ┌──────▼──────┐   ┌──────▼─────────┐   ┌─────────────────────────┐   │
│  │  Strategy    │   │  AI Decision    │   │   Data Providers        │   │
│  │  Engine      │   │  Engine         │   │   (adapters)            │   │
│  │ - SMC        │   │ - Provider-     │   │  - Twelve Data (Gold)       │   │
│  │ - Fibonacci  │   │   agnostic LLM  │   │  - Binance (BTC)         │   │
│  │ - RSI/MACD   │   │   client        │   │  - Finnhub (News/Sent.)  │   │
│  │ - EMA 20/50/ │   │ - Prompt        │   │  - Finnhub (News & Sentiment, sole source)    │   │
│  │   200        │   │   builder       │   │                          │   │
│  └─────────────┘   └─────────────────┘   └─────────────────────────┘   │
│                                                                         │
│  ┌─────────────────────────────────────────────────────────────────┐  │
│  │  Cache / Store: Redis (hot price cache, rate-limit, pub/sub)      │  │
│  │  Postgres (signal history, news cache, audit log)                  │  │
│  └─────────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────┘
```

## 2. Why this shape

- **Adapters for data providers**: Twelve Data and Binance have completely different auth, symbols, and rate limits. Each lives behind a common `PriceProvider` interface so swapping or adding a provider (e.g., Twelve Data) never touches strategy code.
- **Strategy engine is pure functions**: SMC/Fibonacci/RSI/MACD/EMA logic takes a DataFrame in, returns structured findings out. No I/O, no API calls. This makes it unit-testable and lets you backtest by feeding historical candles through the same code path that powers live signals.
- **AI Decision Engine is provider-agnostic**: An abstract `LLMClient` interface with `ClaudeClient` and `OpenAIClient` implementations. The orchestrator builds a structured prompt (JSON-in, JSON-out) so swapping providers is a one-line config change, not a rewrite.
- **Redis sits in front of providers**: premium API keys still have rate limits. Redis caches the latest candle/price snapshot and de-duplicates concurrent requests from multiple connected dashboard clients.
- **WebSocket for push, REST for pull**: charts need a live feed; signal cards, news, and history are fine as polled/request-driven REST. Don't force everything through one transport.
- **Secrets never touch the frontend**: all provider keys and the LLM API key live only in backend env vars, loaded via `pydantic-settings`. The frontend only ever talks to your FastAPI backend.

## 3. Step-by-Step Implementation Plan

### Phase 1 — Foundations (Day 1-2)
1. Scaffold backend (`FastAPI` app, `pydantic-settings` config, Docker).
2. Define core domain models (`Candle`, `Signal`, `NewsItem`, `SMCFinding`) with Pydantic.
3. Stand up Redis + Postgres via `docker-compose`.

### Phase 2 — Data Layer (Day 2-4)
4. Build `PriceProvider` abstract base class.
5. Implement `TwelveDataProvider` (Gold/XAU via REST; polled pseudo-stream since Twelve Data has no free-tier WebSocket).
6. Implement `BinanceProvider` (BTC via REST + WebSocket klines).
7. Implement `NewsProvider` abstraction with `FinnhubNewsProvider` as the sole source, normalize to one `NewsItem` schema, add sentiment scoring (VADER).
8. Add Redis caching layer + rate-limit guard in front of providers.

### Phase 3 — Strategy Engine (Day 4-7)
9. Implement indicator layer using hand-rolled pandas math (Wilder RSI, EMA-based MACD, EMA 20/50/200) — no `pandas-ta`/TA-Lib dependency, avoiding their C-build and numpy-2.0 compatibility issues on managed hosts like Render.
10. Implement Fibonacci module: swing high/low detection (fractal-based), auto-level calculation (0.236…0.786).
11. Implement SMC module: swing structure tracking → BOS/MSS detection, order block identification (last opposing candle before impulsive move).
12. Implement candlestick price-action module: bullish/bearish engulfing, hammer/shooting star (range-relative wick thresholds), doji, morning/evening star — geometric rules on OHLC, not a black-box classifier.
13. Combine into `TechnicalAnalysisEngine.analyze(candles) -> AnalysisResult`.

### Phase 4 — AI Decision Layer (Day 7-9)
13. Define `LLMClient` interface (`generate_decision(prompt) -> TradeDecision`).
14. Implement `ClaudeClient`, `OpenAIClient`.
15. Build structured prompt template: feeds in SMC findings, Fib levels, indicator states, and recent news/sentiment for **both** Gold and BTC, asks for strict JSON output (`asset`, `action`, `confidence`, `risk_reward`, `reasoning`, `invalidation_level`).
16. Validate LLM JSON output against a Pydantic schema; reject/retry on malformed output (never trust raw LLM text in production).

### Phase 5 — API & Realtime (Day 9-11)
17. REST endpoints: `/api/v1/market/{symbol}/candles`, `/api/v1/analysis/{symbol}`, `/api/v1/signal/compare` (Gold vs BTC), `/api/v1/news/{symbol}`.
18. WebSocket endpoint `/ws/prices/{symbol}` broadcasting live ticks via Redis pub/sub.
19. APScheduler jobs: refresh candles every 5–15s, recompute full analysis every 1–5 min, persist signals to Postgres for history/audit.

### Phase 6 — Frontend (Day 11-15)
20. React + Vite + Tailwind scaffold.
21. `PriceChart` component using `lightweight-charts`, overlay Fib levels + OB zones as price lines/rectangles.
22. `SignalCard` component (BUY/SELL/HOLD, confidence meter, reasoning, R:R).
23. `AssetComparePanel` — side-by-side Gold vs BTC signal comparison.
24. `NewsFeed` component with sentiment badges.
25. WebSocket hook (`useLivePrice`) + REST hooks (`useAnalysis`, `useNews`) via `@tanstack/react-query`.

### Phase 7 — Hardening & Deploy (Day 15-18)
26. Add auth (API key or JWT) on backend endpoints if exposing publicly.
27. Rate-limit your own API (`slowapi`) to protect upstream quota.
28. Structured logging + error tracking (Sentry optional).
29. Write `Dockerfile`s for backend/frontend + `docker-compose.yml` (Postgres, Redis, backend, frontend, nginx reverse proxy).
30. CI: lint (`ruff`), type-check (`mypy`), test (`pytest`) on push.

## 4. Security Notes (production checklist)

- All provider/LLM keys in `.env`, never committed; `.env.example` checked in instead.
- CORS locked to your actual frontend origin, not `*`.
- Backend is the only thing holding API keys — frontend never calls Twelve Data/Binance/Finnhub/LLM directly.
- Validate/clamp all LLM output before it reaches the frontend (schema validation, confidence bounds, no free-text injection into HTML).
- Rate-limit public endpoints; add API-key auth if this will be internet-facing.
- Treat AI signals as **decision support, not financial advice** — surface this in the UI (see disclaimer note below).

---
**Disclaimer to bake into the UI**: this system produces automated technical/sentiment analysis, not investment advice. Markets are risky; past patterns (including SMC/Fib setups) do not guarantee future results.
