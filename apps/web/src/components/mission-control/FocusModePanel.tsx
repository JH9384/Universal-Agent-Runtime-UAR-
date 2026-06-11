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

interface FocusModePanelProps {
  onOpenReplay?: (runId: string, recommendationIds?: string[]) => void;
  onOpenEvidence?: (ref: string) => void;
  onSelectTab?: (tab: "health" | "topology" | "replay" | "artifacts") => void;
}

function primarySignal(snapshot: MissionControlSnapshot | null): string {
  const signal = snapshot?.fleet_summary?.top_signal;
  if (signal) return `${signal.title}: ${signal.message}`;
  const pattern = snapshot?.incident_summary?.top_pattern;
  if (pattern) return `${pattern.scope}:${pattern.value}`;
  const warnings = snapshot?.recent_warnings ?? [];
  if (warnings.length) return warnings[0];
  return "No interrupting signal.";
}

function recentChange(snapshot: MissionControlSnapshot | null): string {
  const fleet = snapshot?.fleet_summary;
  const recurrence = snapshot?.incident_summary?.recurring_patterns ?? 0;
  const drift = snapshot?.trust_summary?.drift_count ?? 0;
  if (fleet?.active_signals) {
    return `${fleet.active_signals} fleet signal(s): ${fleet.critical_signals} critical, ${fleet.warning_signals} warning.`;
  }
  if (recurrence > 0) return `${recurrence} recurring pattern(s).`;
  if (drift > 0) return `${drift} trust drift signal(s).`;
  return "No material change detected.";
}

function focusedGuidance(replayRun: string | null, recommendationIds: string[], evidenceRefs: string[]): string {
  if (replayRun && recommendationIds.length) return "Review replay, verify evidence, record outcome.";
  if (replayRun) return "Review replay and confirm whether follow-up is needed.";
  if (evidenceRefs.length) return "Open evidence and decide whether to create/record follow-up.";
  return "Monitor.";
}

export function FocusModePanel({ onOpenReplay, onOpenEvidence, onSelectTab }: FocusModePanelProps) {
  const { data, loading, error, refetch } = useApiFetch<MissionControlSnapshot>(
    "/api/uar/mission-control",
    { interval: 30_000 }
  );

  const topSignal = data?.fleet_summary?.top_signal ?? null;
  const replayRun = topSignal?.linkage?.replay?.run_id ?? topSignal?.latest_run_id ?? null;
  const recommendationIds = topSignal?.linkage?.recommendations ?? [];
  const evidenceRefs = topSignal?.linkage?.evidence_refs ?? [];
  const incidents = topSignal?.linkage?.incidents ?? [];
  const signalText = useMemo(() => primarySignal(data), [data]);
  const changeText = useMemo(() => recentChange(data), [data]);
  const guidance = useMemo(() => focusedGuidance(replayRun, recommendationIds, evidenceRefs), [replayRun, recommendationIds, evidenceRefs]);

  if (loading && !data) return <section className="mission-panel">Loading Focus Mode…</section>;
  if (error) return <section className="mission-panel"><p className="error">Focus Mode failed: {error}</p></section>;

  return (
    <section className="mission-panel mc-boring-panel">
      <header>
        <h2>Focus Mode</h2>
        <button type="button" className="mc-reset-btn" onClick={refetch}>Refresh</button>
      </header>

      <div className="mc-next-action">
        <h3>Operator move</h3>
        <p className="mc-subtext"><strong>{guidance}</strong></p>
      </div>

      <dl>
        <dt>Primary signal</dt>
        <dd>{signalText}</dd>
        <dt>Recent change</dt>
        <dd>{changeText}</dd>
        <dt>Evidence</dt>
        <dd>{evidenceRefs.length ? evidenceRefs.join(", ") : "No evidence refs linked."}</dd>
        <dt>Action</dt>
        <dd>{replayRun ? "Open replay and record outcome." : "Monitor."}</dd>
        <dt>Context</dt>
        <dd>{incidents.length ? `Incident(s): ${incidents.join(", ")}` : "No linked incidents."}</dd>
        <dt>Confidence</dt>
        <dd>{data?.trust_summary?.top_trust_score ?? "No trust score yet."}</dd>
      </dl>

      <div className="mc-briefing-links">
        {replayRun && (
          <button type="button" className="mc-filter-btn" onClick={() => onOpenReplay?.(replayRun, recommendationIds)}>
            ▶ Replay {replayRun.slice(0, 12)}…
          </button>
        )}
        <button type="button" className="mc-filter-btn" onClick={() => onSelectTab?.("health")}>
          Health
        </button>
        <button type="button" className="mc-filter-btn" onClick={() => evidenceRefs[0] ? onOpenEvidence?.(evidenceRefs[0]) : onSelectTab?.("artifacts")}>
          Evidence
        </button>
      </div>

      {evidenceRefs.length > 0 && (
        <div className="mc-evidence-chips" aria-label="Evidence references">
          {evidenceRefs.map((ref) => (
            <button key={ref} type="button" className="mc-link-chip" onClick={() => onOpenEvidence?.(ref)}>
              {ref}
            </button>
          ))}
        </div>
      )}

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
    </section>
  );
}
