# AI Trading Assistant — Gold (XAU/USD) & Bitcoin (BTC/USD)

Full-stack trading dashboard combining Smart Money Concepts (SMC), Fibonacci
retracement, classic indicators (RSI/MACD/EMA), candlestick price-action
patterns (engulfing, hammer, shooting star, doji, morning/evening star), and
news sentiment into an
AI-generated BUY/SELL/HOLD signal with a Gold-vs-Bitcoin comparison.

**Current data sources** (updated for India-region access + Render deploy):
- Gold (XAU/USD): **Twelve Data**
- Bitcoin (BTC/USD): **Twelve Data**
- News + sentiment: **Finnhub** (sole source)
- AI decision layer: **OpenAI** (default; Claude still available via one env var)

See `ARCHITECTURE.md` for the full architecture diagram and implementation
plan. This file covers how to actually deploy it.

## Project layout

```
backend/      FastAPI service: data providers, strategy engine, AI decision layer
frontend/     React + Vite + Tailwind dashboard, Lightweight Charts
render.yaml   Render Blueprint — deploys both services + cache in one step
docker-compose.yml   Optional: still works if you ever run this on a PC with Docker
```

## Deploying to Render (no PC / no Docker needed)

### 1. Push this project to GitHub
Upload the whole folder to a new GitHub repo (GitHub's web uploader works
fine from a phone browser for this — no git CLI required).

### 2. Create the Blueprint on Render
- Render Dashboard → **New** → **Blueprint**
- Connect your GitHub repo
- Render reads `render.yaml` automatically and shows you 3 resources:
  the backend web service, the frontend static site, and a small Key Value
  (Redis-compatible) cache.
- Click **Deploy Blueprint**.

### 3. Fill in your API keys
Render will prompt you for each `sync: false` variable during setup (or
you can add them afterward under each service → **Environment**):

| Variable | Where you get it |
|---|---|
| `TWELVEDATA_API_KEY` | twelvedata.com dashboard |
| `BINANCE_API_KEY` | Binance API Management |
| `BINANCE_API_SECRET` | Binance API Management |
| `FINNHUB_API_KEY` | finnhub.io dashboard |
| `OPENAI_API_KEY` | platform.openai.com |

`LLM_PROVIDER`, `OPENAI_MODEL`, refresh intervals, and rate limits are
already set as plain (non-secret) values in `render.yaml` — you don't need
to touch those unless you want different defaults.

### 4. After first deploy, fix the CORS URL
Render assigns your frontend a URL like
`https://trading-assistant-frontend.onrender.com`. Open the **backend**
service → Environment → update `CORS_ORIGINS` to match that exact URL,
e.g. `["https://trading-assistant-frontend.onrender.com"]`. Save — Render
redeploys the backend automatically.

If your frontend's auto-generated URL differs from the one assumed in
`render.yaml`, also double check the backend's `VITE_API_BASE_URL` value on
the **frontend** service matches the backend's real URL.

### 5. Open the app
Visit your frontend's Render URL. The dashboard should load, pull Gold
candles for both Gold and BTC from Twelve Data, and start showing AI
signals within a minute or two (first analysis cycle needs enough candle
history to compute EMA200, so give it a moment).

## Running locally (optional, needs a PC)

**Backend:**
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then fill in your real keys
uvicorn app.main:app --reload --port 8000
```
You'll also need Redis running locally, or point `REDIS_URL` in `.env` at
a hosted instance (e.g. the same Render Key Value instance, using its
*external* connection URL).

**Frontend:**
```bash
cd frontend
npm install
npm run dev
```
Vite's dev proxy forwards `/api` and `/ws` to `localhost:8000` automatically
(see `vite.config.js`) — no env vars needed for local dev.

## Switching the AI provider

Set `LLM_PROVIDER=openai` or `LLM_PROVIDER=claude` in the backend's env vars
— no code changes needed either way. The decision engine talks to an
abstract `LLMClient` interface (`app/services/ai/base.py`);
`app/services/ai/clients.py` is the only file that knows about the
OpenAI/Anthropic SDKs specifically.

## Key endpoints

| Endpoint | Purpose |
|---|---|
| `GET /api/v1/market/{symbol}/candles` | Raw OHLCV candles |
| `GET /api/v1/analysis/{symbol}` | SMC + Fibonacci + indicators |
| `GET /api/v1/news/{symbol}` | News with sentiment scores |
| `GET /api/v1/signal/{symbol}` | AI trade decision for one asset |
| `GET /api/v1/signal/compare` | **Gold vs BTC head-to-head** |
| `WS /ws/prices/{symbol}` | Live price stream |

`symbol` is `XAUUSD` or `BTCUSD`. `timeframe` query param accepts `M15`,
`H1`, `H4`, `D1`.

## Things to know about this setup

- **No live price push for Gold or BTC.** Twelve Data's free/basic tier has
  no WebSocket stream, so both assets' "live" price polls every 10 seconds
  instead of true push-streaming. Same interface downstream, slightly less
  frequent updates — fine for swing/intraday use, not for scalping.
- **No database wired up yet.** The original design included Postgres for
  signal history/audit logs, but no models or migrations exist for it, so
  it's deliberately left out of `render.yaml` to keep your first deploy
  simple and free. Add it back (a `databases:` block + SQLAlchemy models)
  if you want historical signal tracking later.
- **Render's free tier sleeps on inactivity.** The backend web service will
  spin down after ~15 minutes with no traffic and take ~30-60 seconds to
  wake up on the next request. Fine for personal use; upgrade the plan if
  you need it always-warm.
- **Twelve Data's free tier has a request-per-minute cap.** The backend's
  Redis cache (default 120s TTL on analysis, set via
  `ANALYSIS_REFRESH_INTERVAL_SEC`) exists specifically to keep you under it
  even with multiple browser tabs open.

## Before going further

- Rotate any key that has ever touched a public repo or chat log.
- Keep `CORS_ORIGINS` locked to your actual frontend URL — never `*`.
- Treat all AI signals as decision support, not financial advice.

## Disclaimer

This system produces automated technical and sentiment analysis, not
investment advice. Markets are risky; past patterns do not guarantee future
results.
