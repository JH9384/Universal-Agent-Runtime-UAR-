interface IncidentPattern {
  scope: string;
  value: string;
  recurrence_count: number;
  affected_run_ids: string[];
  latest_run_id?: string | null;
  linked_incident_ids?: string[];
  linked_recommendation_ids?: string[];
  evidence_refs?: string[];
}

export function buildRecurrenceNotes(pattern: IncidentPattern | null | undefined): string[] {
  if (!pattern) return [];

  const latestRun = pattern.latest_run_id || pattern.affected_run_ids[0] || "unknown";
  const incidents = pattern.linked_incident_ids?.length
    ? pattern.linked_incident_ids.join(", ")
    : "none linked";
  const recommendations = pattern.linked_recommendation_ids?.length
    ? pattern.linked_recommendation_ids.join(", ")
    : "none linked";
  const evidence = pattern.evidence_refs?.length
    ? pattern.evidence_refs.slice(0, 3).join(", ")
    : `run:${latestRun}`;

  return [
    `Recurrence scope: ${pattern.scope}:${pattern.value}.`,
    `Latest run: ${latestRun}.`,
    `Recurrence count: ${pattern.recurrence_count}.`,
    `Incident context: ${incidents}.`,
    `Recommendation context: ${recommendations}.`,
    `Evidence context: ${evidence}.`,
  ];
}

export type { IncidentPattern };
