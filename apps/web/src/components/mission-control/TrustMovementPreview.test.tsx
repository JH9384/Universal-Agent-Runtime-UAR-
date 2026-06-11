import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { TrustMovementPreview } from './TrustMovementPreview'

describe('TrustMovementPreview', () => {
  it('renders read-only trust movement for linked recommendation evidence', () => {
    render(
      <TrustMovementPreview
        recommendationIds={['rec-1']}
        runId="run-brief-1"
        movements={[
          {
            recommendation_id: 'rec-1',
            run_id: 'run-brief-1',
            before: 0.72,
            after: 0.81,
            delta: 0.09,
            outcome_type: 'resolved',
            evidence_refs: ['run:run-brief-1'],
          },
        ]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Trust movement' })).toBeInTheDocument()
    expect(screen.getByText(/rec-1/)).toBeInTheDocument()
    expect(screen.getAllByText(/run-brief-1/).length).toBeGreaterThan(0)
    expect(screen.getByText(/resolved/i)).toBeInTheDocument()
  })

  it('renders an empty read-only state when no movement is available yet', () => {
    render(
      <TrustMovementPreview
        recommendationIds={['rec-1']}
        runId="run-brief-1"
        movements={[]}
      />,
    )

    expect(screen.getByRole('heading', { name: 'Trust movement' })).toBeInTheDocument()
    expect(screen.getByText(/No trust movement/i)).toBeInTheDocument()
  })
})
