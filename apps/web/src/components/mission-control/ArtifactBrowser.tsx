import { useEffect, useState, useRef, useCallback } from "react";
import { dashboardApi } from "../../api/dashboard";
import type { RunRecord } from "../../api/dashboard";
import { useApiFetch } from "../../hooks/useApiFetch";
import { buildEvidencePackPreview } from "../../utils/evidencePackPreview";
import { downloadMarkdown, evidencePackFilename } from "../../utils/downloadMarkdown";

type StatusFilter = "all" | "completed" | "failed" | "running" | "pending";

interface MissionControlSnapshot {
  incident_summary?: {
    status: string;
    recurring_patterns: number;
    top_pattern: {
      scope: string;
      value: string;
      recurrence_count: number;
      affected_run_ids: string[];
      latest_run_id?: string | null;
      linked_incident_ids?: string[];
      linked_recommendation_ids?: string[];
      evidence_refs?: string[];
    } | null;
  } | null;
}

interface ArtifactBrowserProps {
  initialEvidenceRef?: string;
}

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  running: "#3b82f6",
  failed: "#ef4444",
  pending: "#f59e0b",
};

function runIdFromEvidenceRef(ref?: string): string | null {
  if (!ref) return null;
  return ref.startsWith("run:") ? ref.slice(4) : null;
}

export function ArtifactBrowser({ initialEvidenceRef }: ArtifactBrowserProps) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [filter, setFilter] = useState<StatusFilter>("all");
  const [evidenceRef, setEvidenceRef] = useState(initialEvidenceRef ?? "");
  const [copied, setCopied] = useState(false);
  const [downloaded, setDownloaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const mountedRef = useRef(true);
  const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const downloadTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const { data: missionControl } = useApiFetch<MissionControlSnapshot>(
    "/api/uar/mission-control",
    { interval: 30_000 }
  );

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
    if (initialEvidenceRef) setEvidenceRef(initialEvidenceRef);
  }, [initialEvidenceRef]);

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
      if (downloadTimerRef.current) clearTimeout(downloadTimerRef.current);
    };
  }, []);

  const highlightedRunId = runIdFromEvidenceRef(evidenceRef);
  const visibleByStatus = filter === "all" ? runs : runs.filter((r) => r.status === filter);
  const visible = highlightedRunId
    ? visibleByStatus.filter((r) => r.run_id.includes(highlightedRunId))
    : visibleByStatus;

  const counts = runs.reduce<Record<string, number>>((acc, r) => {
    acc[r.status] = (acc[r.status] ?? 0) + 1;
    return acc;
  }, {});

  const evidencePreview = buildEvidencePackPreview(runs, Date.now(), {
    incidentSummary: missionControl?.incident_summary,
  });
  const recurrence = evidencePreview.top_recurrence;

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

  function downloadEvidenceMarkdown() {
    downloadMarkdown(evidencePackFilename(evidencePreview.generated_at), evidencePreview.markdown);
    setDownloaded(true);
    downloadTimerRef.current = setTimeout(() => {
      if (mountedRef.current) setDownloaded(false);
      downloadTimerRef.current = null;
    }, 1500);
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

      <div className="mc-next-action">
        <h3>Evidence focus</h3>
        <p className="mc-subtext"><strong>{evidenceRef ? `Review linked evidence ${evidenceRef}.` : "Review evidence pack preview, then export markdown for release or incident review."}</strong></p>
        {evidenceRef && (
          <button type="button" className="mc-filter-btn" onClick={() => setEvidenceRef("")}>Clear evidence focus</button>
        )}
      </div>

      <label className="mc-field-label" htmlFor="artifact-evidence-ref">Evidence ref</label>
      <input
        id="artifact-evidence-ref"
        type="search"
        value={evidenceRef}
        onChange={(e) => setEvidenceRef(e.target.value)}
        placeholder="Filter by evidence ref, e.g. run:abc123…"
        className="mc-search-input"
      />

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
          <dt>Recurrence</dt>
          <dd>{evidencePreview.recurrence_count}</dd>
        </dl>
        {recurrence && (
          <div className="mc-briefing-section">
            <h3>Top recurrence</h3>
            <p className="mc-subtext"><strong>{recurrence.scope}:{recurrence.value}</strong></p>
            <p className="mc-meta--xs">Latest run: {recurrence.latest_run_id ?? "none"}</p>
            <p className="mc-meta--xs">Evidence refs: {recurrence.evidence_refs?.join(", ") || "none"}</p>
          </div>
        )}
        <div className="mc-briefing-links">
          <button type="button" className="mc-filter-btn" onClick={copyEvidenceMarkdown}>
            {copied ? "Copied" : "Copy Evidence Markdown"}
          </button>
          <button type="button" className="mc-filter-btn" onClick={downloadEvidenceMarkdown}>
            {downloaded ? "Downloaded" : "Download Evidence Markdown"}
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
          const highlighted = highlightedRunId && r.run_id.includes(highlightedRunId);
          return (
            <li key={r.run_id} className={highlighted ? "mc-artifact-row mc-artifact-row--highlight" : "mc-artifact-row"} style={{ "--mc-status-color": color } as React.CSSProperties}>
              <div className="mc-row mc-row--sm-gap">
                <span className="mc-dot mc-dot--sm" aria-hidden="true" />
                <code className="mc-run-id">{r.run_id}</code>
                <span className="mc-status-badge">{r.status}</span>
              </div>
              {highlighted && <p className="mc-status-summary--ok">Selected evidence match: run:{r.run_id}</p>}
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
