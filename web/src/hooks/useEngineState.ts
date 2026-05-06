import { useEffect, useRef, useState } from "react";
import type { EnginePayload } from "@/lib/types";

export function useEngineState(): EnginePayload | null {
  const [state, setState] = useState<EnginePayload | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    let cancelled = false;
    let retryTimer: number | null = null;

    const connect = () => {
      // Vite dev: same-origin /ws is proxied to ws://localhost:8080/ws
      const proto = window.location.protocol === "https:" ? "wss" : "ws";
      const ws = new WebSocket(`${proto}://${window.location.host}/ws`);
      wsRef.current = ws;

      ws.onmessage = (ev) => {
        try {
          setState(JSON.parse(ev.data) as EnginePayload);
        } catch (e) {
          console.error("Bad payload:", e);
        }
      };

      ws.onclose = () => {
        if (!cancelled) {
          retryTimer = window.setTimeout(connect, 1000);
        }
      };

      ws.onerror = () => ws.close();
    };

    connect();
    return () => {
      cancelled = true;
      if (retryTimer) window.clearTimeout(retryTimer);
      wsRef.current?.close();
    };
  }, []);

  return state;
}
