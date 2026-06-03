import { useEffect, useState, useRef, useCallback } from "react";
import { api } from "../../api/client";
import type { RunRecord } from "../../api/client";

type StatusFilter = "all" | "completed" | "failed" | "running" | "pending";

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  running: "#3b82f6",
  failed: "#ef4444",
  pending: "#f59e0b",
};

export function ArtifactBrowser() {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);

  const fetchData = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await api.listRuns(signal ? { signal } : undefined);
      if (!mountedRef.current) return;
      setRuns(data);
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

  const visible = filter === "all" ? runs : runs.filter((r) => r.status === filter);

  const counts = runs.reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] ?? 0) + 1;
    return acc;
  }, {});

  if (loading) {
    return (
      <section aria-label="Artifact browser" className="mission-panel">
        <header><h2>Artifacts</h2></header>
        <p>Loading...</p>
      </section>
    );
  }

  if (error) {
    return (
      <section aria-label="Artifact browser" className="mission-panel">
        <header><h2>Artifacts</h2></header>
        <p className="error">{error}</p>
      </section>
    );
  }

  const FILTERS: StatusFilter[] = ["all", "completed", "failed", "running", "pending"];

  return (
    <section aria-label="Artifact browser" className="mission-panel">
      <header>
        <h2>Artifacts</h2>
        <span aria-live="polite">{visible.length} / {runs.length} records</span>
      </header>

      <div className="mc-filter-bar">
        {FILTERS.map((f) => {
          const active = filter === f;
          const color = f === "all" ? "#66fcf1" : (STATUS_COLOR[f] ?? "#94a3b8");
          return (
            <button
              key={f}
              type="button"
              onClick={() => setFilter(f)}
              className={active ? "mc-filter-btn mc-filter-btn--active" : "mc-filter-btn"}
              style={{
                "--mc-color": active ? "#0b0c10" : color,
                "--mc-bg": active ? color : "#0b0c10",
                "--mc-border": active ? color : "#1f2833",
              } as import("react").CSSProperties}
              aria-pressed={active ? "true" : "false"}
            >
              {f}{f !== "all" && counts[f] ? ` (${counts[f]})` : f === "all" ? ` (${runs.length})` : ""}
            </button>
          );
        })}
      </div>

      <ul>
        {visible.map((r) => {
          const color = STATUS_COLOR[r.status] ?? "#94a3b8";
          return (
            <li key={r.run_id} style={{ "--mc-status-color": color } as import("react").CSSProperties}>
              <div className="mc-row mc-row--sm-gap">
                <span className="mc-dot mc-dot--sm" aria-hidden="true" />
                <code className="mc-run-id">{r.run_id}</code>
                <span className="mc-status-badge">{r.status}</span>
              </div>
              {r.skills && r.skills.length > 0 && (
                <div className="mc-skills">{r.skills.join(", ")}</div>
              )}
            </li>
          );
        })}
        {visible.length === 0 && (
          <li key="empty" className="mc-meta--muted">No records match this filter.</li>
        )}
      </ul>
    </section>
  );
}
