import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RecurrenceCorrelationPreview } from './RecurrenceCorrelationPreview'

describe('RecurrenceCorrelationPreview', () => {
  it('renders read-only recurrence correlation for linked recommendation evidence', () => {
    render(
      <RecurrenceCorrelationPreview
        recommendationIds={['rec-1']}
        runId="run-brief-1"
        correlations={[
          {
            recommendation_id: 'rec-1',
            run_id: 'run-brief-1',
            outcome_type: 'resolved',
            evidence_refs: ['run:run-brief-1'],
            trust_delta: 0.09,
            later_recurrence_count: 0,
            later_recurrence_run_ids: [],
            correlation_status: 'improved',
          },
        ]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Recurrence correlation' })).toBeInTheDocument()
    expect(screen.getByText(/rec-1/)).toBeInTheDocument()
    expect(screen.getAllByText(/run-brief-1/).length).toBeGreaterThan(0)
    expect(screen.getByText(/Improved/i)).toBeInTheDocument()
    expect(screen.getByText(/Later recurrence: 0/i)).toBeInTheDocument()
    expect(screen.getByText(/Trust delta:/i)).toHaveTextContent('+0.09')
  })

  it('renders an empty read-only state when no correlation is available yet', () => {
    render(
      <RecurrenceCorrelationPreview
        recommendationIds={['rec-1']}
        runId="run-brief-1"
        correlations={[]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Recurrence correlation' })).toBeInTheDocument()
    expect(screen.getByText(/No recurrence correlation/i)).toBeInTheDocument()
  })
})
