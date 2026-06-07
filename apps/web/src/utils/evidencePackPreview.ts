import type { RunRecord } from '../api/dashboard'

interface EvidencePackPreview {
  status: 'nominal' | 'warning' | 'critical'
  generated_at: number
  total_records: number
  failed_records: number
  running_records: number
  completed_records: number
  top_failed_run_id: string | null
  evidence_refs: string[]
  markdown: string
}

function _status(failed: number, running: number): EvidencePackPreview['status'] {
  if (failed >= 3) return 'critical'
  if (failed > 0 || running > 0) return 'warning'
  return 'nominal'
}

export function buildEvidencePackPreview(runs: RunRecord[], generatedAt = Date.now()): EvidencePackPreview {
  const failed = runs.filter((r) => r.status === 'failed')
  const running = runs.filter((r) => r.status === 'running')
  const completed = runs.filter((r) => r.status === 'completed')
  const status = _status(failed.length, running.length)
  const topFailedRun = failed[0] ?? null
  const evidenceRefs = runs.slice(0, 10).map((r) => `run:${r.run_id}`)
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
    '',
    'Evidence refs:',
    ...(evidenceRefs.length ? evidenceRefs.map((ref) => `- \`${ref}\``) : ['- `none`']),
  ]

  return {
    status,
    generated_at: generatedAt,
    total_records: runs.length,
    failed_records: failed.length,
    running_records: running.length,
    completed_records: completed.length,
    top_failed_run_id: topFailedRun?.run_id ?? null,
    evidence_refs: evidenceRefs,
    markdown: lines.join('\n'),
  }
}
