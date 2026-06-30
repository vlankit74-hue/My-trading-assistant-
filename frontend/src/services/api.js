// In local dev (npm run dev), VITE_API_BASE_URL is unset, so this falls
// back to a relative path — Vite's dev proxy (vite.config.js) forwards
// that to localhost:8000. On Render, the frontend and backend are two
// separate services with separate URLs, so VITE_API_BASE_URL is set as a
// build-time env var pointing at the backend's Render URL (see render.yaml).
const API_ROOT = import.meta.env.VITE_API_BASE_URL || "";
const API_BASE = `${API_ROOT}/api/v1`;

async function request(path, opts) {
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API error ${res.status}: ${body || res.statusText}`);
  }
  return res.json();
}

export const api = {
  getCandles: (symbol, timeframe = "H1", count = 200) =>
    request(`/market/${symbol}/candles?timeframe=${timeframe}&count=${count}`),

  getAnalysis: (symbol, timeframe = "H1") =>
    request(`/analysis/${symbol}?timeframe=${timeframe}`),

  getNews: (symbol) => request(`/news/${symbol}`),

  getSignal: (symbol, timeframe = "H1") =>
    request(`/signal/${symbol}?timeframe=${timeframe}`),

  compareSignal: (timeframe = "H1") =>
    request(`/signal/compare?timeframe=${timeframe}`),
};
