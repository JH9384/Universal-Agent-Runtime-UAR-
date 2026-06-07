import { describe, expect, it } from 'vitest'
import { buildRecurrenceNotes } from './recurrenceNotes'


describe('buildRecurrenceNotes', () => {
  it('returns no notes without a pattern', () => {
    expect(buildRecurrenceNotes(null)).toEqual([])
  })

  it('builds compact recurrence notes from a pattern', () => {
    const notes = buildRecurrenceNotes({
      scope: 'service',
      value: 'svc-a',
      recurrence_count: 2,
      affected_run_ids: ['r2', 'r1'],
      latest_run_id: 'r2',
      linked_incident_ids: ['inc-1'],
      linked_recommendation_ids: ['rec-1'],
      evidence_refs: ['run:r2', 'run:r1'],
    })

    expect(notes).toEqual([
      'Recurrence scope: service:svc-a.',
      'Latest run: r2.',
      'Recurrence count: 2.',
      'Incident context: inc-1.',
      'Recommendation context: rec-1.',
      'Evidence context: run:r2, run:r1.',
    ])
  })

  it('falls back when optional fields are missing', () => {
    const notes = buildRecurrenceNotes({
      scope: 'skill',
      value: 'parse_pdf',
      recurrence_count: 3,
      affected_run_ids: ['r3'],
    })

    expect(notes).toContain('Latest run: r3.')
    expect(notes).toContain('Incident context: none linked.')
    expect(notes).toContain('Recommendation context: none linked.')
    expect(notes).toContain('Evidence context: run:r3.')
  })
})
