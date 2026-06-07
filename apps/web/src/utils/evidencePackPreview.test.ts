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
})
