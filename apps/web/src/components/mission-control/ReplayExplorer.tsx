import { useEffect, useRef, useState, useCallback } from "react";
import { dashboardApi } from "../../api/dashboard";
import { RecommendationOutcomeCapture } from "./RecommendationOutcomeCapture";
import { TrustMovementPreview } from "./TrustMovementPreview";
import type { RunRecord } from "../../api/dashboard";

const STATUS_COLOR: Record<string, string> = {
  completed: "#22c55e",
  running: "#3b82f6",
  failed: "#ef4444",
  pending: "#f59e0b",
};

interface ReplayExplorerProps {
  initialRunId?: string;
  onOpenEvidence?: (ref: string) => void;
  recommendationIds?: string[];
}

function runTimestamp(record: RunRecord): string {
  const ts = record.timestamp ?? record.created_at;
  if (!ts) return "unknown";
  const value = ts > 10_000_000_000 ? ts : ts * 1000;
  return new Date(value).toISOString();
}

function runGuidance(record: RunRecord): string {
  if (record.status === "failed") return "Inspect failure path and attach evidence before closing.";
  if (record.status === "running") return "Monitor until completion before recording an outcome.";
  if (record.status === "completed") return "Use as replay evidence if linked to an operator decision.";
  return "Check run state before taking action.";
}

export function ReplayExplorer({ initialRunId, onOpenEvidence, recommendationIds = [] }: ReplayExplorerProps) {
  const [runs, setRuns] = useState<RunRecord[]>([]);
  const [filter, setFilter] = useState(initialRunId ?? "");
  const [selectedRunId, setSelectedRunId] = useState<string | null>(initialRunId ?? null);
  const [copied, setCopied] = useState<string | null>(null);
  const [evidencePackRunId, setEvidencePackRunId] = useState<string | null>(null);
  const [evidencePackMarkdown, setEvidencePackMarkdown] = useState<string | null>(null);
  const [evidencePackLoading, setEvidencePackLoading] = useState(false);
  const [evidencePackError, setEvidencePackError] = useState<string | null>(null);
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
    if (initialRunId) {
      setFilter(initialRunId);
      setSelectedRunId(initialRunId);
    }
  }, [initialRunId]);

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

  async function openEvidencePack(runId: string) {
    setEvidencePackRunId(runId);
    setEvidencePackMarkdown(null);
    setEvidencePackError(null);
    setEvidencePackLoading(true);

    const requestedRunId = runId;

    try {
      const payload = await dashboardApi.evidencePack(runId);
      if (!mountedRef.current || requestedRunId !== runId) return;

      setEvidencePackMarkdown(
        typeof payload.markdown === "string" && payload.markdown.trim()
          ? payload.markdown
          : "No Evidence Pack markdown returned.",
      );
    } catch (err) {
      if (!mountedRef.current || requestedRunId !== runId) return;

      setEvidencePackError(
        err instanceof Error ? err.message : "Evidence Pack request failed.",
      );
    } finally {
      if (mountedRef.current) {
        setEvidencePackLoading(false);
      }
    }
  }

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

  const normalizedFilter = filter.trim();

  const visible = normalizedFilter
    ? runs.filter(
        (r) =>
          r.run_id.includes(normalizedFilter) ||
          r.status.includes(normalizedFilter)
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

      <div className="mc-next-action">
        <h3>Investigation flow</h3>
        <p className="mc-subtext"><strong>Select a run, inspect status/skills, then open its evidence reference if it supports an operator outcome.</strong></p>
      </div>

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
          const autoSelected = normalizedFilter === r.run_id && visible.length === 1;
          const selected = selectedRunId === r.run_id || autoSelected;
          const evidenceRef = `run:${r.run_id}`;
          return (
            <li key={r.run_id} className="mc-replay-row" style={{ "--mc-status-color": color } as React.CSSProperties}>
              <div
                className="mc-row"
                onClick={() => setSelectedRunId(selectedRunId === r.run_id ? null : r.run_id)}
                role="presentation"
              >
                <span className="mc-dot" aria-hidden="true" />
                <button
                  type="button"
                  className="mc-run-select"
                  aria-expanded={selected ? "true" : "false"}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedRunId(selectedRunId === r.run_id ? null : r.run_id);
                  }}
                >
                  <code className="mc-run-id">{r.run_id}</code>
                </button>
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
                  onClick={(event) => {
                    event.stopPropagation();
                    copyId(r.run_id);
                  }}
                  title="Copy run ID"
                  className={copied === r.run_id ? "mc-copy-btn mc-copy-btn--copied" : "mc-copy-btn"}
                >
                  {copied === r.run_id ? "✓" : "⧉"}
                </button>
              </div>
              {selected && (
                <div className="mc-run-detail">
                  <dl>
                    <dt>Operator meaning</dt>
                    <dd>{runGuidance(r)}</dd>
                    <dt>Timestamp</dt>
                    <dd>{runTimestamp(r)}</dd>
                    <dt>Goal</dt>
                    <dd>{r.goal_id ?? "unknown"}</dd>
                    <dt>Evidence ref</dt>
                    <dd>{evidenceRef}</dd>
                  </dl>
                  {r.skills && r.skills.length > 0 && (
                    <p className="mc-skills">Skills: {r.skills.join(", ")}</p>
                  )}
                  <div className="mc-briefing-links">
                    <button type="button" className="mc-filter-btn" onClick={() => onOpenEvidence?.(evidenceRef)}>
                      Open Evidence
                    </button>
                    <button type="button" className="mc-filter-btn" onClick={() => openEvidencePack(r.run_id)}>
                      Evidence Pack
                    </button>
                    <button type="button" className="mc-filter-btn" onClick={() => copyId(r.run_id)}>
                      Copy Run ID
                    </button>
                  </div>
                </div>
              )}
            </li>
          );
        })}
        {visible.length === 0 && (
          <li key="empty" className="mc-meta--muted">
            {filter ? "No matching runs." : "No runs yet."}
          </li>
        )}
      </ul>
      {(evidencePackRunId || evidencePackLoading || evidencePackError || evidencePackMarkdown) && (
        <section className="mc-evidence-pack-panel" aria-label="Evidence Pack preview">
          <div className="mc-section-header">
            <div>
              <h3>Evidence Pack</h3>
              <p className="mc-subtext">
                Read-only Evidence Pack v2 preview for <code>{evidencePackRunId}</code>.
              </p>
            </div>
            <button
              type="button"
              className="mc-filter-btn"
              onClick={() => {
                setEvidencePackRunId(null);
                setEvidencePackMarkdown(null);
                setEvidencePackError(null);
              }}
            >
              Close
            </button>
          </div>

          {evidencePackLoading && <p className="mc-meta--xs">Loading Evidence Pack…</p>}
          {evidencePackError && <p className="mc-status-summary--fail">{evidencePackError}</p>}
          {evidencePackMarkdown && <pre className="mc-evidence-preview">{evidencePackMarkdown}</pre>}

          <div className="mc-briefing-section">
            <h3>Outcome handoff</h3>
            {recommendationIds.length > 0 ? (
              <RecommendationOutcomeCapture
                recommendationIds={recommendationIds}
                runId={evidencePackRunId}
              />
            ) : (
              <p className="mc-status-summary--warn">
                Outcome capture is waiting for recommendation linkage. This Evidence Pack is run-linked, but no recommendation ID is available in Replay Explorer yet.
              </p>
            )}
          </div>

          <TrustMovementPreview
            recommendationIds={recommendationIds}
            runId={evidencePackRunId}
            movements={[]}
          />
        </section>
      )}
    </section>
  );
}
