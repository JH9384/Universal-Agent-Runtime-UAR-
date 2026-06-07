import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { RecommendationOutcomeCapture } from './RecommendationOutcomeCapture'

beforeEach(() => {
  vi.restoreAllMocks()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: vi.fn().mockResolvedValue({ status: 'ok' }),
  }))
})

describe('RecommendationOutcomeCapture', () => {
  it('renders nothing when no recommendation ids exist', () => {
    const { container } = render(<RecommendationOutcomeCapture recommendationIds={[]} />)
    expect(container).toBeEmptyDOMElement()
  })

  it('posts resolved outcome through existing recommendation outcome endpoint', async () => {
    const user = userEvent.setup()
    const onRecorded = vi.fn()

    render(
      <RecommendationOutcomeCapture
        recommendationIds={['rec-1']}
        runId="run-1"
        onRecorded={onRecorded}
      />
    )

    await user.click(screen.getByRole('button', { name: 'Resolved' }))

    expect(fetch).toHaveBeenCalledWith(
      `${window.location.origin}/api/uar/recommendations/outcome`,
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({
          recommendation_id: 'rec-1',
          outcome_type: 'resolved',
          run_id: 'run-1',
          source: 'operator_briefing',
        }),
      })
    )
    expect(await screen.findByText('Recorded resolved for rec-1')).toBeInTheDocument()
    expect(onRecorded).toHaveBeenCalled()
  })

  it('allows selecting another linked recommendation id', async () => {
    const user = userEvent.setup()
    render(
      <RecommendationOutcomeCapture
        recommendationIds={['rec-1', 'rec-2']}
        runId="run-2"
      />
    )

    await user.selectOptions(screen.getByLabelText('Recommendation'), 'rec-2')
    await user.click(screen.getByRole('button', { name: 'Recurred' }))

    expect(fetch).toHaveBeenCalledWith(
      `${window.location.origin}/api/uar/recommendations/outcome`,
      expect.objectContaining({
        body: JSON.stringify({
          recommendation_id: 'rec-2',
          outcome_type: 'recurred',
          run_id: 'run-2',
          source: 'operator_briefing',
        }),
      })
    )
  })
})
