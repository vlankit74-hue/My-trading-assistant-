import { useQuery } from "@tanstack/react-query";
import { api } from "../services/api";

export function useCandles(symbol, timeframe) {
  return useQuery({
    queryKey: ["candles", symbol, timeframe],
    queryFn: () => api.getCandles(symbol, timeframe),
    // Twelve Data's free plan allows only 8 calls/minute TOTAL, shared
    // across Gold + BTC + the backend's own background polling. This
    // endpoint has no server-side cache in front of it, so keep this slow
    // — 60s rather than 15s — to leave headroom for everything else
    // pulling from the same quota.
    refetchInterval: 60_000,
  });
}

export function useAnalysis(symbol, timeframe) {
  return useQuery({
    queryKey: ["analysis", symbol, timeframe],
    queryFn: () => api.getAnalysis(symbol, timeframe),
    refetchInterval: 60_000,
  });
}

export function useNews(symbol) {
  return useQuery({
    queryKey: ["news", symbol],
    queryFn: () => api.getNews(symbol),
    refetchInterval: 120_000,
  });
}

export function useSignalCompare(timeframe) {
  return useQuery({
    queryKey: ["compare", timeframe],
    queryFn: () => api.compareSignal(timeframe),
    refetchInterval: 90_000,
  });
}
