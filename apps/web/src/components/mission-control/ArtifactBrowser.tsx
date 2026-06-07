import { useEffect, useState, useRef, useCallback } from "react";
import { dashboardApi } from "../../api/dashboard";
import type { RunRecord } from "../../api/dashboard";
import { buildEvidencePackPreview } from "../../utils/evidencePackPreview";

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
  const [copied, setCopied] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const fetchData = useCallback(async (signal?: AbortSignal) => {
    try {
      const data = await dashboardApi.listRuns(signal ? { signal } : undefined);
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

  useEffect(() => {
    return () => {
      if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
    };
  }, []);

  const visible = filter === "all" ? runs : runs.filter((r) => r.status === filter);

  const counts = runs.reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] ?? 0) + 1;
    return acc;
  }, {});

  const evidencePreview = buildEvidencePackPreview(runs);

  function copyEvidenceMarkdown() {
    navigator.clipboard.writeText(evidencePreview.markdown).then(() => {
      if (!mountedRef.current) return;
      setCopied(true);
      copyTimerRef.current = setTimeout(() => {
        if (mountedRef.current) setCopied(false);
        copyTimerRef.current = null;
      }, 1500);
    }).catch(() => {
      if (mountedRef.current) setCopied(false);
    });
  }

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

      <div className="mc-briefing-section" style={{ marginTop: 0, paddingTop: 0, borderTop: "none" }}>
        <h3>Evidence Pack v2 Preview</h3>
        <dl>
          <dt>Status</dt>
          <dd>{evidencePreview.status}</dd>
          <dt>Total</dt>
          <dd>{evidencePreview.total_records}</dd>
          <dt>Failed</dt>
          <dd>{evidencePreview.failed_records}</dd>
          <dt>Running</dt>
          <dd>{evidencePreview.running_records}</dd>
          <dt>Completed</dt>
          <dd>{evidencePreview.completed_records}</dd>
          <dt>Top failed run</dt>
          <dd>{evidencePreview.top_failed_run_id ?? "none"}</dd>
        </dl>
        <div className="mc-briefing-links">
          <button type="button" className="mc-filter-btn" onClick={copyEvidenceMarkdown}>
            {copied ? "Copied" : "Copy Evidence Markdown"}
          </button>
        </div>
        <pre className="mc-evidence-preview">{evidencePreview.markdown}</pre>
      </div>

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
              } as React.CSSProperties}
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
            <li key={r.run_id} style={{ "--mc-status-color": color } as React.CSSProperties}>
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
