import { useMemo } from "react";
import { useApiFetch } from "../../hooks/useApiFetch";
import { RecommendationOutcomeCapture } from "./RecommendationOutcomeCapture";
import { IncidentRecurrenceSummary } from "./IncidentRecurrenceSummary";

interface FleetSignalLinkage {
  replay?: { run_id?: string | null; available?: boolean } | null;
  incidents?: string[];
  recommendations?: string[];
  evidence_refs?: string[];
}

interface FleetSignal {
  id: string;
  level: string;
  scope: string;
  title: string;
  message: string;
  latest_run_id?: string | null;
  linkage?: FleetSignalLinkage;
}

interface MissionControlSnapshot {
  fleet_summary?: {
    status: string;
    active_signals: number;
    critical_signals: number;
    warning_signals: number;
    top_signal: FleetSignal | null;
  } | null;
  incident_summary?: any;
  runtime_health?: { score?: number; tier?: string } | null;
  certification?: { score?: number; level?: string } | null;
  trust_summary?: {
    top_trusted?: string | null;
    top_trust_score?: number | null;
    drift_count?: number;
  } | null;
  recent_warnings?: string[];
}

interface OperatorBriefingPanelProps {
  onOpenReplay?: (runId: string) => void;
  onSelectTab?: (tab: "health" | "topology" | "replay" | "artifacts") => void;
}

function _priority(snapshot: MissionControlSnapshot | null): string {
  const fleetStatus = snapshot?.fleet_summary?.status ?? "nominal";
  const runtimeTier = String(snapshot?.runtime_health?.tier ?? "").toLowerCase();
  const certLevel = String(snapshot?.certification?.level ?? "").toLowerCase();
  if ([fleetStatus, runtimeTier, certLevel].some((v) => ["critical", "failed", "unstable", "degraded"].includes(v))) {
    return "critical";
  }
  if (fleetStatus === "warning") return "warning";
  return "nominal";
}

export function OperatorBriefingPanel({ onOpenReplay, onSelectTab }: OperatorBriefingPanelProps) {
  const { data, loading, error, refetch } = useApiFetch<MissionControlSnapshot>(
    "/api/uar/mission-control",
    { interval: 30_000 }
  );

  const priority = useMemo(() => _priority(data), [data]);
  const topSignal = data?.fleet_summary?.top_signal ?? null;
  const replayRun = topSignal?.linkage?.replay?.run_id ?? topSignal?.latest_run_id ?? null;
  const recommendationIds = topSignal?.linkage?.recommendations ?? [];
  const incidentIds = topSignal?.linkage?.incidents ?? [];
  const evidenceRefs = topSignal?.linkage?.evidence_refs ?? [];

  if (loading && !data) return <section className="mission-panel">Loading briefing…</section>;
  if (error) return <section className="mission-panel"><p className="error">Briefing failed: {error}</p></section>;

  return (
    <section className="mission-panel mc-briefing-panel">
      <header>
        <h2>Operator Briefing</h2>
        <button type="button" className="mc-reset-btn" onClick={refetch}>Refresh</button>
      </header>

      <div className={`mc-briefing-priority mc-briefing-priority--${priority}`}>
        {priority.toUpperCase()}
      </div>

      <dl>
        <dt>Fleet</dt>
        <dd>{data?.fleet_summary?.status ?? "nominal"}</dd>
        <dt>Signals</dt>
        <dd>{data?.fleet_summary?.active_signals ?? 0}</dd>
        <dt>Runtime</dt>
        <dd>{data?.runtime_health?.tier ?? "unknown"} · {data?.runtime_health?.score ?? "—"}</dd>
        <dt>Certification</dt>
        <dd>{data?.certification?.level ?? "unknown"} · {data?.certification?.score ?? "—"}</dd>
        <dt>Top trust</dt>
        <dd>{data?.trust_summary?.top_trusted ?? "—"}</dd>
        <dt>Warnings</dt>
        <dd>{data?.recent_warnings?.length ?? 0}</dd>
      </dl>

      <div className="mc-briefing-section">
        <h3>Top signal</h3>
        {topSignal ? (
          <div>
            <p className="mc-subtext"><strong>{topSignal.title}</strong></p>
            <p className="mc-subtext">{topSignal.message}</p>
            <div className="mc-briefing-links">
              {replayRun && (
                <button type="button" className="mc-filter-btn" onClick={() => onOpenReplay?.(replayRun)}>
                  ▶ Replay {replayRun.slice(0, 12)}…
                </button>
              )}
              <button type="button" className="mc-filter-btn" onClick={() => onSelectTab?.("health")}>
                Open Health
              </button>
              <button type="button" className="mc-filter-btn" onClick={() => onSelectTab?.("artifacts")}>
                Evidence
              </button>
            </div>
            <p className="mc-meta--xs">Incidents: {incidentIds.length ? incidentIds.join(", ") : "none"}</p>
            <p className="mc-meta--xs">Recommendations: {recommendationIds.length ? recommendationIds.join(", ") : "none"}</p>
            <p className="mc-meta--xs">Evidence refs: {evidenceRefs.length ? evidenceRefs.join(", ") : "none"}</p>
          </div>
        ) : (
          <p className="mc-status-summary--ok">No interrupting fleet signal. Monitor fleet health.</p>
        )}
      </div>

      <IncidentRecurrenceSummary
        incidentSummary={data?.incident_summary}
        onOpenReplay={onOpenReplay}
        onSelectTab={onSelectTab}
      />

      <RecommendationOutcomeCapture
        recommendationIds={recommendationIds}
        runId={replayRun}
        onRecorded={refetch}
      />

      {data?.recent_warnings && data.recent_warnings.length > 0 && (
        <div className="mc-briefing-section">
          <h3>Warnings</h3>
          <ul>
            {data.recent_warnings.slice(0, 5).map((warning, index) => (
              <li key={`${warning}-${index}`}>{warning}</li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
