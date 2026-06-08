import { buildRecurrenceNotes } from "../../utils/recurrenceNotes";

interface IncidentPattern {
  id: string;
  scope: string;
  value: string;
  recurrence_count: number;
  affected_run_ids: string[];
  latest_run_id?: string | null;
  linked_incident_ids?: string[];
  linked_recommendation_ids?: string[];
  evidence_refs?: string[];
}

interface IncidentSummary {
  status: string;
  recurring_patterns: number;
  top_pattern: IncidentPattern | null;
}

interface IncidentRecurrenceSummaryProps {
  incidentSummary?: IncidentSummary | null;
  onOpenReplay?: (runId: string) => void;
  onSelectTab?: (tab: "health" | "topology" | "replay" | "artifacts") => void;
}

export function IncidentRecurrenceSummary({ incidentSummary, onOpenReplay, onSelectTab }: IncidentRecurrenceSummaryProps) {
  const pattern = incidentSummary?.top_pattern ?? null;
  if (!pattern) return null;

  const latestRun = pattern.latest_run_id ?? pattern.affected_run_ids?.[0] ?? null;
  const incidents = pattern.linked_incident_ids ?? [];
  const recommendations = pattern.linked_recommendation_ids ?? [];
  const evidenceRefs = pattern.evidence_refs ?? [];
  const notes = buildRecurrenceNotes(pattern);

  return (
    <div className="mc-briefing-section">
      <h3>Top recurrence</h3>
      <p className="mc-subtext">
        <strong>{pattern.scope}:{pattern.value}</strong>
      </p>
      <p className="mc-subtext">
        {pattern.recurrence_count} recurring failure(s) across {pattern.affected_run_ids.length} run(s).
      </p>
      <div className="mc-briefing-links">
        {latestRun && (
          <button type="button" className="mc-filter-btn" onClick={() => onOpenReplay?.(latestRun)}>
            ▶ Replay {latestRun.slice(0, 12)}…
          </button>
        )}
        <button type="button" className="mc-filter-btn" onClick={() => onSelectTab?.("artifacts")}>
          Evidence
        </button>
      </div>
      <p className="mc-meta--xs">Incident IDs: {incidents.length ? incidents.join(", ") : "none"}</p>
      <p className="mc-meta--xs">Recommendation IDs: {recommendations.length ? recommendations.join(", ") : "none"}</p>
      <p className="mc-meta--xs">Evidence refs: {evidenceRefs.length ? evidenceRefs.join(", ") : "none"}</p>
      {notes.length > 0 && (
        <ul className="mc-recurrence-notes">
          {notes.map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

export type { IncidentSummary, IncidentPattern };
