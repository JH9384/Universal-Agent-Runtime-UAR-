import { describe, expect, it } from 'vitest'
import { buildEvidencePackPreview } from './evidencePackPreview'


describe('buildEvidencePackPreview', () => {
  it('returns nominal preview for completed records', () => {
    const preview = buildEvidencePackPreview([
      { run_id: 'r1', status: 'completed', skills: ['echo'] },
    ], 123)

    expect(preview.status).toBe('nominal')
    expect(preview.total_records).toBe(1)
    expect(preview.completed_records).toBe(1)
    expect(preview.top_failed_run_id).toBeNull()
    expect(preview.recurrence_count).toBe(0)
    expect(preview.markdown).toContain('Fleet status: **nominal**')
  })

  it('returns warning preview for one failed record', () => {
    const preview = buildEvidencePackPreview([
      { run_id: 'r1', status: 'failed', skills: ['echo'] },
      { run_id: 'r2', status: 'completed', skills: ['echo'] },
    ], 456)

    expect(preview.status).toBe('warning')
    expect(preview.failed_records).toBe(1)
    expect(preview.top_failed_run_id).toBe('r1')
    expect(preview.evidence_refs).toEqual(['run:r1', 'run:r2'])
    expect(preview.markdown).toContain('Top failed run: `r1`')
  })

  it('returns critical preview for three or more failed records', () => {
    const preview = buildEvidencePackPreview([
      { run_id: 'r1', status: 'failed' },
      { run_id: 'r2', status: 'failed' },
      { run_id: 'r3', status: 'failed' },
    ])

    expect(preview.status).toBe('critical')
    expect(preview.failed_records).toBe(3)
  })

  it('includes recurrence context from Mission Control incident summary', () => {
    const preview = buildEvidencePackPreview(
      [
        { run_id: 'r1', status: 'completed' },
      ],
      789,
      {
        incidentSummary: {
          status: 'active',
          recurring_patterns: 1,
          top_pattern: {
            scope: 'service',
            value: 'svc-a',
            recurrence_count: 2,
            affected_run_ids: ['r3', 'r2'],
            latest_run_id: 'r3',
            linked_incident_ids: ['inc-1'],
            linked_recommendation_ids: ['rec-1'],
            evidence_refs: ['run:r3', 'run:r2'],
          },
        },
      }
    )

    expect(preview.status).toBe('warning')
    expect(preview.recurrence_count).toBe(1)
    expect(preview.top_recurrence?.value).toBe('svc-a')
    expect(preview.evidence_refs).toEqual(['run:r1', 'run:r3', 'run:r2'])
    expect(preview.markdown).toContain('Top recurrence:')
    expect(preview.markdown).toContain('Value: `svc-a`')
    expect(preview.markdown).toContain('Incident IDs: `inc-1`')
  })
})
