import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Dashboard } from './Dashboard'

const mockUseApiFetch = vi.fn()

vi.mock('../hooks/useApiFetch', () => ({
  useApiFetch: (...args: unknown[]) => mockUseApiFetch(...args),
}))

vi.mock('../api/dashboard', () => ({
  dashboardApi: {
    listRuns: vi.fn().mockResolvedValue([
      { run_id: 'run-brief-1', status: 'failed', skills: ['echo'] },
      { run_id: 'run-other', status: 'completed', skills: ['echo'] },
    ]),
  },
}))

beforeEach(() => {
  mockUseApiFetch.mockReset()
})

describe('Dashboard operator loop', () => {
  it('moves from briefing top signal to replay tab with run filter', async () => {
    const user = userEvent.setup()
    mockUseApiFetch.mockReturnValue({
      data: {
        fleet_summary: {
          status: 'critical',
          active_signals: 1,
          critical_signals: 1,
          warning_signals: 0,
          top_signal: {
            id: 'fleet:service:svc-a',
            level: 'critical',
            scope: 'service',
            title: 'Service signal: svc-a',
            message: '3 failures across 3 runs',
            latest_run_id: 'run-brief-1',
            linkage: {
              replay: { run_id: 'run-brief-1', available: true },
              incidents: [],
              recommendations: [],
              evidence_refs: ['run:run-brief-1'],
            },
          },
        },
        runtime_health: { score: 95, tier: 'Healthy' },
        certification: { score: 90, level: 'Gold' },
        trust_summary: { top_trusted: 'cache', top_trust_score: 0.82, drift_count: 0 },
        recent_warnings: [],
      },
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<Dashboard />)

    expect(screen.getByRole('tab', { name: 'Briefing' })).toHaveAttribute('aria-selected', 'true')
    await user.click(screen.getByRole('button', { name: /Replay run-brief/i }))

    expect(screen.getByRole('tab', { name: 'Replay' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByDisplayValue('run-brief-1')).toBeInTheDocument()
  })
})
