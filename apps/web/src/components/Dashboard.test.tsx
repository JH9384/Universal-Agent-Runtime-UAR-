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
      { run_id: 'run-focus-1', status: 'failed', skills: ['echo'] },
      { run_id: 'run-recur-1', status: 'failed', skills: ['echo'] },
      { run_id: 'run-other', status: 'completed', skills: ['echo'] },
    ]),
    evidencePack: vi.fn().mockResolvedValue({
      status: 'ok',
      run_id: 'run-brief-1',
      evidence_pack: {
        evidence_pack_id: 'evidence-pack:run-brief-1',
        run_id: 'run-brief-1',
      },
      markdown: '# Evidence Pack v2 — run-brief-1\n\nSignal -> Mission Control -> Replay -> Evidence Pack -> Outcome -> Trust Movement',
    }),
  },
}))

function _missionControl(runId = 'run-brief-1') {
  return {
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
        latest_run_id: runId,
        linkage: {
          replay: { run_id: runId, available: true },
          incidents: [],
          recommendations: ['rec-1'],
          evidence_refs: [`run:${runId}`],
        },
      },
    },
    incident_summary: {
      status: 'nominal',
      recurring_patterns: 0,
      top_pattern: null,
    },
    runtime_health: { score: 95, tier: 'Healthy' },
    certification: { score: 90, level: 'Gold' },
    trust_summary: { top_trusted: 'cache', top_trust_score: 0.82, drift_count: 0 },
    recent_warnings: [],
  }
}

function _missionControlWithRecurrence() {
  return {
    fleet_summary: {
      status: 'nominal',
      active_signals: 0,
      critical_signals: 0,
      warning_signals: 0,
      top_signal: null,
    },
    incident_summary: {
      status: 'active',
      recurring_patterns: 1,
      top_pattern: {
        id: 'incident:service:svc-recur',
        scope: 'service',
        value: 'svc-recur',
        recurrence_count: 2,
        affected_run_ids: ['run-recur-1', 'run-recur-old'],
        latest_run_id: 'run-recur-1',
        linked_incident_ids: ['inc-recur'],
        linked_recommendation_ids: ['rec-recur'],
        evidence_refs: ['run:run-recur-1'],
      },
    },
    runtime_health: { score: 95, tier: 'Healthy' },
    certification: { score: 90, level: 'Gold' },
    trust_summary: { top_trusted: 'cache', top_trust_score: 0.82, drift_count: 0 },
    recent_warnings: [],
  }
}

beforeEach(() => {
  mockUseApiFetch.mockReset()
})

describe('Dashboard operator loop', () => {
  it('moves from briefing top signal to replay tab with run filter', async () => {
    const user = userEvent.setup()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl('run-brief-1'),
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

  it('moves from briefing evidence to artifacts with evidence focus', async () => {
    const user = userEvent.setup()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl('run-brief-1'),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<Dashboard />)

    await user.click(screen.getByRole('button', { name: 'Evidence' }))

    expect(screen.getByRole('tab', { name: 'Artifacts' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByDisplayValue('run:run-brief-1')).toBeInTheDocument()
    expect(screen.getByText('Review linked evidence run:run-brief-1.')).toBeInTheDocument()
  })

  it('moves from focus mode to replay tab with run filter', async () => {
    const user = userEvent.setup()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl('run-focus-1'),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<Dashboard />)

    await user.click(screen.getByRole('tab', { name: 'Focus' }))
    expect(screen.getByRole('tab', { name: 'Focus' })).toHaveAttribute('aria-selected', 'true')
    await user.click(screen.getByRole('button', { name: /Replay run-focus/i }))

    expect(screen.getByRole('tab', { name: 'Replay' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByDisplayValue('run-focus-1')).toBeInTheDocument()
  })

  it('moves from briefing recurrence to replay tab with run filter', async () => {
    const user = userEvent.setup()
    mockUseApiFetch.mockReturnValue({
      data: _missionControlWithRecurrence(),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<Dashboard />)

    expect(screen.getByText('Top recurrence')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Replay run-recur/i }))

    expect(screen.getByRole('tab', { name: 'Replay' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByDisplayValue('run-recur-1')).toBeInTheDocument()
  })

  it('moves from replay detail to artifacts with generated run evidence', async () => {
    const user = userEvent.setup()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl('run-brief-1'),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<Dashboard />)

    await user.click(screen.getByRole('button', { name: /Replay run-brief/i }))
    await screen.findByDisplayValue('run-brief-1')
    await user.click(await screen.findByRole('button', { name: 'Open Evidence' }))

    expect(screen.getByRole('tab', { name: 'Artifacts' })).toHaveAttribute('aria-selected', 'true')
    expect(await screen.findByDisplayValue('run:run-brief-1')).toBeInTheDocument()
  })

  it('renders Evidence Pack markdown from Replay Explorer action', async () => {
    const user = userEvent.setup()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl('run-brief-1'),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<Dashboard />)

    await user.click(screen.getByRole('button', { name: /Replay run-brief/i }))
    await screen.findByDisplayValue('run-brief-1')
    await user.click(await screen.findByRole('button', { name: 'run-brief-1' }))
    await user.click(await screen.findByRole('button', { name: 'Evidence Pack' }))

    const preview = await screen.findByRole('region', { name: 'Evidence Pack preview' })
    expect(preview).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Evidence Pack' })).toBeInTheDocument()
    expect(preview.textContent).toContain('Evidence Pack v2')
    expect(preview.textContent).toContain('run-brief-1')
    expect(preview.textContent).toContain('Signal -> Mission Control -> Replay -> Evidence Pack -> Outcome -> Trust Movement')
  })
  it('carries recommendation IDs from briefing replay into replay outcome handoff', async () => {
    const user = userEvent.setup()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl('run-brief-1'),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<Dashboard />)

    await user.click(screen.getByRole('button', { name: /Replay run-brief/i }))
    await screen.findByDisplayValue('run-brief-1')
    await user.click(await screen.findByRole('button', { name: 'Evidence Pack' }))

    expect(await screen.findByText('Outcome handoff')).toBeInTheDocument()
    expect(await screen.findByLabelText('Recommendation')).toHaveValue('rec-1')
    expect(screen.getByRole('button', { name: 'Resolved' })).toBeInTheDocument()
  })

})
