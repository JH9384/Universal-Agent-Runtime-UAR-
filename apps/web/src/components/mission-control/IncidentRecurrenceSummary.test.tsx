import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { IncidentRecurrenceSummary } from './IncidentRecurrenceSummary'

const summary = {
  status: 'active',
  recurring_patterns: 1,
  top_pattern: {
    id: 'incident:service:svc-a',
    scope: 'service',
    value: 'svc-a',
    recurrence_count: 3,
    affected_run_ids: ['r3', 'r2', 'r1'],
    latest_run_id: 'r3',
    linked_incident_ids: ['inc-1'],
    linked_recommendation_ids: ['rec-1'],
    evidence_refs: ['run:r3', 'run:r2', 'run:r1'],
  },
}

describe('IncidentRecurrenceSummary', () => {
  it('renders nothing without a top pattern', () => {
    const { container } = render(<IncidentRecurrenceSummary incidentSummary={{ status: 'nominal', recurring_patterns: 0, top_pattern: null }} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('renders top recurrence context', () => {
    render(<IncidentRecurrenceSummary incidentSummary={summary} />)

    expect(screen.getByText('Top recurrence')).toBeInTheDocument()
    expect(screen.getByText('service:svc-a')).toBeInTheDocument()
    expect(screen.getByText('3 recurring failure(s) across 3 run(s).')).toBeInTheDocument()
    expect(screen.getByText('Incident IDs: inc-1')).toBeInTheDocument()
    expect(screen.getByText('Recommendation IDs: rec-1')).toBeInTheDocument()
    expect(screen.getByText('Evidence refs: run:r3, run:r2, run:r1')).toBeInTheDocument()
  })

  it('opens replay for latest recurrence run', async () => {
    const user = userEvent.setup()
    const onOpenReplay = vi.fn()

    render(<IncidentRecurrenceSummary incidentSummary={summary} onOpenReplay={onOpenReplay} />)

    await user.click(screen.getByRole('button', { name: /Replay r3/i }))

    expect(onOpenReplay).toHaveBeenCalledWith('r3')
  })

  it('routes evidence action to artifacts', async () => {
    const user = userEvent.setup()
    const onSelectTab = vi.fn()

    render(<IncidentRecurrenceSummary incidentSummary={summary} onSelectTab={onSelectTab} />)

    await user.click(screen.getByRole('button', { name: 'Evidence' }))

    expect(onSelectTab).toHaveBeenCalledWith('artifacts')
  })
})
