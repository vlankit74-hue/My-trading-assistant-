import { useEffect, useRef, useState } from "react";

// In local dev, VITE_API_BASE_URL is unset, so the WS connects to the
// current page's own host (Vite's dev proxy forwards /ws to localhost:8000).
// On Render, this resolves to the backend service's actual host, since the
// frontend is a separate static site with its own domain.
const API_ROOT = import.meta.env.VITE_API_BASE_URL || "";

function buildWsUrl(symbol) {
  if (API_ROOT) {
    const wsRoot = API_ROOT.replace(/^http/, "ws");
    return `${wsRoot}/ws/prices/${symbol}`;
  }
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws/prices/${symbol}`;
}

/**
 * Subscribes to /ws/prices/{symbol} and keeps the latest tick in state.
 * Reconnects with backoff on drop so a brief network blip doesn't leave
 * the dashboard silently stale.
 */
export function useLivePrice(symbol) {
  const [price, setPrice] = useState(null);
  const [connected, setConnected] = useState(false);
  const retryDelay = useRef(1000);

  useEffect(() => {
    let socket;
    let closedByEffect = false;

    const connect = () => {
      socket = new WebSocket(buildWsUrl(symbol));

      socket.onopen = () => {
        setConnected(true);
        retryDelay.current = 1000;
      };

      socket.onmessage = (event) => {
        try {
          const tick = JSON.parse(event.data);
          setPrice(tick.close);
        } catch {
          // ignore malformed frame
        }
      };

      socket.onclose = () => {
        setConnected(false);
        if (!closedByEffect) {
          setTimeout(connect, retryDelay.current);
          retryDelay.current = Math.min(retryDelay.current * 2, 15_000);
        }
      };

      socket.onerror = () => socket.close();
    };

    connect();

    return () => {
      closedByEffect = true;
      socket?.close();
    };
  }, [symbol]);

  return { price, connected };
}
