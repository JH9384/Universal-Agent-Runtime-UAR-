import { useEffect, useRef, useState, useCallback } from "react";
import { api } from "../../api/client";

interface CircuitEntry {
  name: string;
  state: string;
  failures: number;
}

const STATE_COLOR: Record<string, string> = {
  closed: "#22c55e",
  open: "#ef4444",
  half_open: "#f59e0b",
};

export function TopologyGraph() {
  const [circuits, setCircuits] = useState<CircuitEntry[]>([]);
  const [resetting, setResetting] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const inFlightRef = useRef(0);
  const resetInFlightRef = useRef(false);
  const abortCtrlRef = useRef<AbortController | null>(null);

  const load = useCallback(async (signal?: AbortSignal, force?: boolean) => {
    if (!force && inFlightRef.current > 0) return;
    inFlightRef.current += 1;
    try {
      const data = await api.circuitBreakers(signal ? { signal } : undefined);
      if (!mountedRef.current) return;
      const mapped: CircuitEntry[] = Object.entries(data.circuits || {}).map(
        ([name, info]) => ({
          name,
          state: info.state ?? "unknown",
          failures: info.failures ?? 0,
        })
      );
      setCircuits(mapped);
      setError(null);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      if (mountedRef.current) setError(String(err));
    } finally {
      inFlightRef.current -= 1;
      if (mountedRef.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    const abortCtrl = new AbortController();
    abortCtrlRef.current = abortCtrl;

    load(abortCtrl.signal);
    const timeoutId = setInterval(() => load(abortCtrl.signal), 5000);
    return () => {
      mountedRef.current = false;
      abortCtrl.abort();
      clearInterval(timeoutId);
      abortCtrlRef.current = null;
    };
  }, [load]);

  function handleReset(name: string) {
    if (resetInFlightRef.current) return;
    resetInFlightRef.current = true;
    setResetting(name);

    const signal = abortCtrlRef.current?.signal;
    setLoading(true);
    api
      .resetCircuitBreaker(name, signal ? { signal } : undefined)
      .then(() => {
        if (!mountedRef.current) return;
        if (abortCtrlRef.current) {
          return load(abortCtrlRef.current.signal, true);
        } else {
          return load(undefined, true);
        }
      })
      .catch((err) => {
        if ((err as Error)?.name === "AbortError") return;
        if (mountedRef.current) setError(String(err));
      })
      .finally(() => {
        resetInFlightRef.current = false;
        if (mountedRef.current) {
          setResetting((prev) => (prev === name ? null : prev));
          setLoading(false);
        }
      });
  }

  const openCount = circuits.filter((c) => c.state === "open" || c.state === "half_open").length;

  if (loading) {
    return (
      <section aria-label="Topology graph" className="mission-panel">
        <header><h2>Topology</h2></header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Topology graph" className="mission-panel">
        <header><h2>Topology</h2></header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Topology graph" className="mission-panel">
      <header>
        <h2>Topology</h2>
        <span className={openCount > 0 ? "mc-status-summary--warn" : "mc-status-summary--ok"} aria-live="polite">
          {openCount > 0 ? `${openCount} open` : "All closed"}
        </span>
      </header>

      <p className="mc-subtext">
        Circuit Breakers — {circuits.length} registered
      </p>

      <ul>
        {circuits.map((c) => {
          const color = STATE_COLOR[c.state] ?? "#94a3b8";
          return (
            <li key={c.name} className="mc-row mc-row--padded" style={{ "--mc-status-color": color } as React.CSSProperties}>
              <span className="mc-dot" aria-hidden="true" />
              <span className="mc-subtext" style={{ "--mc-flex": "1", marginBottom: 0 } as React.CSSProperties}>{c.name}</span>
              <span className="mc-status-badge--xs">
                {c.state.replaceAll("_", "-")}
              </span>
              {c.failures > 0 && (
                <span className="mc-meta--warn">{c.failures}✗</span>
              )}
              {c.state === "open" && (
                <button
                  type="button"
                  onClick={() => handleReset(c.name)}
                  disabled={resetting === c.name}
                  title="Reset circuit breaker"
                  className="mc-reset-btn"
                >
                  {resetting === c.name ? "…" : "Reset"}
                </button>
              )}
            </li>
          );
        })}
        {circuits.length === 0 && (
          <li key="empty" className="mc-meta--muted">No circuit breakers registered.</li>
        )}
      </ul>
    </section>
  );
}
