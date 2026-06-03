import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import { RecommendationPanel } from '../RecommendationPanel'

const originalFetch = globalThis.fetch

describe('FeedbackButtons', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('prevents rapid-fire clicks by disabling buttons during submission', async () => {
    let resolveFetch: (value: Response) => void = () => {}
    globalThis.fetch = vi.fn().mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve
        })
    )

    // Pre-load recommendations so panel is ready
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        generated_at: Date.now(),
        hours: 24,
        runs_analyzed: 10,
        trust_ranking_enabled: false,
        recommendations: [
          {
            recommendation_id: 'rec-1',
            category: 'remediate',
            priority: 'high',
            confidence: 0.85,
            base_confidence: 0.85,
            adaptive_modifier: 1.0,
            trust_score: 0.7,
            title: 'Test Recommendation',
            description: 'Test description',
            source: 'test',
            affected_runs: [],
          },
        ],
        trust: null,
        sources: { recurring_patterns: 0, recovery_paths: 0, topology_points: 0, governance_periods: 0 },
      }),
    }).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve
        })
    )

    render(<RecommendationPanel />)
    await act(async () => {})

    // Wait for recommendations to load
    await waitFor(() => {
      expect(screen.getByText('Test Recommendation')).toBeInTheDocument()
    })

    const acceptBtn = screen.getByText('Accept')

    // First click triggers fetch
    fireEvent.click(acceptBtn)

    // Button should be disabled immediately while request is in flight
    expect(acceptBtn).toBeDisabled()

    // Resolve the pending fetch
    resolveFetch({ ok: true } as Response)

    // After resolution, button should show "Accepted" state
    await waitFor(() => {
      expect(screen.queryByText('Accepted')).toBeInTheDocument()
    })
  })

  it('ignores duplicate clicks while a request is pending', async () => {
    let resolveFetch: (value: Response) => void = () => {}
    globalThis.fetch = vi.fn().mockResolvedValueOnce({
      ok: true,
      json: async () => ({
        generated_at: Date.now(),
        hours: 24,
        runs_analyzed: 10,
        trust_ranking_enabled: false,
        recommendations: [
          {
            recommendation_id: 'rec-1',
            category: 'remediate',
            priority: 'high',
            confidence: 0.85,
            base_confidence: 0.85,
            adaptive_modifier: 1.0,
            trust_score: 0.7,
            title: 'Test Recommendation',
            description: 'Test description',
            source: 'test',
            affected_runs: [],
          },
        ],
        trust: null,
        sources: { recurring_patterns: 0, recovery_paths: 0, topology_points: 0, governance_periods: 0 },
      }),
    }).mockImplementation(
      () =>
        new Promise((resolve) => {
          resolveFetch = resolve
        })
    )

    render(<RecommendationPanel />)
    await act(async () => {})

    await waitFor(() => {
      expect(screen.getByText('Test Recommendation')).toBeInTheDocument()
    })

    const acceptBtn = screen.getByText('Accept')

    // Multiple rapid clicks
    fireEvent.click(acceptBtn)
    fireEvent.click(acceptBtn)
    fireEvent.click(acceptBtn)

    // Should only have called fetch once (the panel load), plus one feedback call
    const feedbackCalls = (globalThis.fetch as ReturnType<typeof vi.fn>).mock.calls.filter(
      (call: unknown[]) => String(call[0]).includes('/feedback')
    )
    expect(feedbackCalls.length).toBe(1)

    resolveFetch({ ok: true } as Response)

    await waitFor(() => {
      expect(screen.queryByText('Accepted')).toBeInTheDocument()
    })
  })
})
