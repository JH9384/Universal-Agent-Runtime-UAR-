import { useEffect, useState, useRef, useCallback } from "react";
import { dashboardApi } from "../../api/dashboard";
import type { RunRecord } from "../../api/dashboard";

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  running: "#3b82f6",
  failed: "#ef4444",
  pending: "#f59e0b",
};

function relativeTime(ts: number | undefined): string {
  if (!ts) return "—";
  const diff = Math.floor((Date.now() - ts) / 1000);
  if (diff < 60) return `${diff}s ago`;
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  return `${Math.floor(diff / 3600)}h ago`;
}

export function RuntimeTimeline() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await dashboardApi.listRuns(signal ? { signal } : undefined);
      if (!mountedRef.current) return;
      setRuns(data.slice(0, 25));
      setError(null);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
      if (mountedRef.current) setError(String(err));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;
    setLoading(true);
    let timeoutId: ReturnType<typeof setTimeout> | undefined;
    let inFlight = false;
    const abortCtrl = new AbortController();

    function tick() {
      if (inFlight) return;
      inFlight = true;
      fetchData(abortCtrl.signal).finally(() => {
        inFlight = false;
        if (mountedRef.current) setLoading(false);
      });
    }

    tick();
    timeoutId = setInterval(tick, 5000);
    return () => {
      mountedRef.current = false;
      abortCtrl.abort();
      clearInterval(timeoutId);
    };
  }, [fetchData]);

  if (loading) {
    return (
      <section aria-label="Runtime timeline" className="mission-panel">
        <header><h2>Runtime Timeline</h2></header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Runtime timeline" className="mission-panel">
        <header><h2>Runtime Timeline</h2></header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Runtime timeline" className="mission-panel">
      <header>
        <h2>Runtime Timeline</h2>
        <span aria-live="polite">{runs.length} runs</span>
      </header>
      <ul>
        {runs.map((r) => {
          const color = STATUS_COLOR[r.status] ?? "#94a3b8";
          const ts = r.created_at ?? r.timestamp;
          return (
            <li key={r.run_id} className="mc-row" style={{ "--mc-status-color": color } as React.CSSProperties}>
              <span className="mc-dot" aria-hidden="true" />
              <code className="mc-run-id">
                {r.run_id.slice(0, 12)}
              </code>
              <span className="mc-status-badge">
                {r.status}
              </span>
              <span className="mc-meta">
                {relativeTime(ts)}
              </span>
            </li>
          );
        })}
        {runs.length === 0 && (
          <li key="empty" className="mc-meta--muted">No runs yet.</li>
        )}
      </ul>
    </section>
  );
}
