import type { RunRecord } from '../api/dashboard'

interface IncidentPatternPreview {
  scope: string
  value: string
  recurrence_count: number
  affected_run_ids: string[]
  latest_run_id?: string | null
  linked_incident_ids?: string[]
  linked_recommendation_ids?: string[]
  evidence_refs?: string[]
}

interface IncidentSummaryPreview {
  status: string
  recurring_patterns: number
  top_pattern: IncidentPatternPreview | null
}

interface EvidencePackPreviewOptions {
  incidentSummary?: IncidentSummaryPreview | null
}

interface EvidencePackPreview {
  status: 'nominal' | 'warning' | 'critical'
  generated_at: number
  total_records: number
  failed_records: number
  running_records: number
  completed_records: number
  top_failed_run_id: string | null
  recurrence_count: number
  top_recurrence: IncidentPatternPreview | null
  evidence_refs: string[]
  markdown: string
}

function _status(failed: number, running: number, recurrenceCount: number): EvidencePackPreview['status'] {
  if (failed >= 3 || recurrenceCount >= 2) return 'critical'
  if (failed > 0 || running > 0 || recurrenceCount > 0) return 'warning'
  return 'nominal'
}

function _unique(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean)))
}

export function buildEvidencePackPreview(
  runs: RunRecord[],
  generatedAt = Date.now(),
  options: EvidencePackPreviewOptions = {}
): EvidencePackPreview {
  const failed = runs.filter((r) => r.status === 'failed')
  const running = runs.filter((r) => r.status === 'running')
  const completed = runs.filter((r) => r.status === 'completed')
  const topRecurrence = options.incidentSummary?.top_pattern ?? null
  const recurrenceCount = options.incidentSummary?.recurring_patterns ?? 0
  const status = _status(failed.length, running.length, recurrenceCount)
  const topFailedRun = failed[0] ?? null
  const runEvidenceRefs = runs.slice(0, 10).map((r) => `run:${r.run_id}`)
  const recurrenceEvidenceRefs = topRecurrence?.evidence_refs ?? []
  const evidenceRefs = _unique([...runEvidenceRefs, ...recurrenceEvidenceRefs])
  const lines = [
    '# UAR Evidence Pack v2 Preview',
    '',
    `Generated at: \`${generatedAt}\``,
    '',
    `Fleet status: **${status}**`,
    `Total records: **${runs.length}**`,
    `Failed records: **${failed.length}**`,
    `Running records: **${running.length}**`,
    `Completed records: **${completed.length}**`,
    `Top failed run: \`${topFailedRun?.run_id ?? 'none'}\``,
    `Recurring patterns: **${recurrenceCount}**`,
    '',
  ]

  if (topRecurrence) {
    lines.push(
      'Top recurrence:',
      `- Scope: \`${topRecurrence.scope}\``,
      `- Value: \`${topRecurrence.value}\``,
      `- Count: \`${topRecurrence.recurrence_count}\``,
      `- Latest run: \`${topRecurrence.latest_run_id ?? 'none'}\``,
      `- Incident IDs: \`${topRecurrence.linked_incident_ids?.join(', ') || 'none'}\``,
      `- Recommendation IDs: \`${topRecurrence.linked_recommendation_ids?.join(', ') || 'none'}\``,
      ''
    )
  }

  lines.push(
    'Evidence refs:',
    ...(evidenceRefs.length ? evidenceRefs.map((ref) => `- \`${ref}\``) : ['- `none`'])
  )

  return {
    status,
    generated_at: generatedAt,
    total_records: runs.length,
    failed_records: failed.length,
    running_records: running.length,
    completed_records: completed.length,
    top_failed_run_id: topFailedRun?.run_id ?? null,
    recurrence_count: recurrenceCount,
    top_recurrence: topRecurrence,
    evidence_refs: evidenceRefs,
    markdown: lines.join('\n'),
  }
}
