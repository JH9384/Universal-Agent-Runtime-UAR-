import { useEffect, useRef, useState, useCallback } from "react";
import { dashboardApi } from "../../api/dashboard";
import type { RunRecord } from "../../api/dashboard";

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  running: "#3b82f6",
  failed: "#ef4444",
  pending: "#f59e0b",
};

export function ReplayExplorer() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [filter, setFilter] = useState("");
  const [copied, setCopied] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await dashboardApi.listRuns(signal ? { signal } : undefined);
      if (!mountedRef.current) return;
      setRuns(data.slice(0, 50));
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
    timeoutId = setInterval(tick, 10_000);
    return () => {
      mountedRef.current = false;
      abortCtrl.abort();
      clearInterval(timeoutId);
    };
  }, [fetchData]);

  function copyId(id: string) {
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    navigator.clipboard.writeText(id).then(() => {
      if (!mountedRef.current) return;
      setCopied(id);
      copyTimerRef.current = setTimeout(() => {
        if (!mountedRef.current) return;
        setCopied((prev) => (prev === id ? null : prev));
        copyTimerRef.current = null;
      }, 1500);
    }).catch(() => {
      if (!mountedRef.current) return;
      setCopied((prev) => (prev === id ? null : prev));
    });
  }

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  const visible = filter.trim()
    ? runs.filter(
        (r) =>
          r.run_id.includes(filter.trim()) ||
          r.status.includes(filter.trim())
      )
    : runs;

  if (loading) {
    return (
      <section aria-label="Replay explorer" className="mission-panel">
        <header><h2>Replay Explorer</h2></header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Replay explorer" className="mission-panel">
        <header><h2>Replay Explorer</h2></header>
        <p className="error">{error}</p>
      </section>
    );
  }

  return (
    <section aria-label="Replay explorer" className="mission-panel">
      <header>
        <h2>Replay Explorer</h2>
        <span aria-live="polite">{visible.length} / {runs.length} runs</span>
      </header>

      <input
        type="search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder="Filter by run ID or status…"
        className="mc-search-input"
      />

      <ul>
        {visible.map((r) => {
          const color = STATUS_COLOR[r.status] ?? "#94a3b8";
          return (
            <li key={r.run_id} className="mc-row" style={{ "--mc-status-color": color } as React.CSSProperties}>
              <span className="mc-dot" aria-hidden="true" />
              <code className="mc-run-id">{r.run_id}</code>
              <span className="mc-status-badge">
                {r.status}
              </span>
              {r.skills && r.skills.length > 0 && (
                <span className="mc-skill-count">
                  {r.skills.length} skills
                </span>
              )}
              <button
                type="button"
                onClick={() => copyId(r.run_id)}
                title="Copy run ID"
                className={copied === r.run_id ? "mc-copy-btn mc-copy-btn--copied" : "mc-copy-btn"}
              >
                {copied === r.run_id ? "✓" : "⧉"}
              </button>
            </li>
          );
        })}
        {visible.length === 0 && (
          <li key="empty" className="mc-meta--muted">
            {filter ? "No matching runs." : "No runs yet."}
          </li>
        )}
      </ul>
    </section>
  );
}
