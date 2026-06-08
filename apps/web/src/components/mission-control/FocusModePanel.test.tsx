import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { FocusModePanel } from './FocusModePanel'

const mockUseApiFetch = vi.fn()

vi.mock('../../hooks/useApiFetch', () => ({
  useApiFetch: (...args: unknown[]) => mockUseApiFetch(...args),
}))

function _snapshot(topSignal: Record<string, unknown> | null = null, incidentSummary: Record<string, unknown> | null = null) {
  return {
    fleet_summary: {
      status: topSignal ? 'critical' : 'nominal',
      active_signals: topSignal ? 1 : 0,
      critical_signals: topSignal ? 1 : 0,
      warning_signals: 0,
      top_signal: topSignal,
    },
    incident_summary: incidentSummary,
    runtime_health: { score: 95, tier: 'Healthy' },
    certification: { score: 90, level: 'Gold' },
    trust_summary: { top_trusted: 'cache', top_trust_score: 0.82, drift_count: 0 },
    recent_warnings: [],
  }
}

const recurrence = {
  status: 'active',
  recurring_patterns: 1,
  top_pattern: {
    id: 'incident:service:svc-focus',
    scope: 'service',
    value: 'svc-focus',
    recurrence_count: 2,
    affected_run_ids: ['fr2', 'fr1'],
    latest_run_id: 'fr2',
    linked_incident_ids: ['inc-focus'],
    linked_recommendation_ids: ['rec-focus'],
    evidence_refs: ['run:fr2', 'run:fr1'],
  },
}

beforeEach(() => {
  mockUseApiFetch.mockReset()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: vi.fn().mockResolvedValue({ status: 'ok' }),
  }))
})

describe('FocusModePanel', () => {
  it('renders simplified nominal state', () => {
    mockUseApiFetch.mockReturnValue({
      data: _snapshot(),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<FocusModePanel />)

    expect(screen.getByText('Focus Mode')).toBeInTheDocument()
    expect(screen.getByText('Primary signal')).toBeInTheDocument()
    expect(screen.getByText('No interrupting signal.')).toBeInTheDocument()
    expect(screen.getByText('Monitor.')).toBeInTheDocument()
  })

  it('renders top signal and opens replay', async () => {
    const user = userEvent.setup()
    const onOpenReplay = vi.fn()
    mockUseApiFetch.mockReturnValue({
      data: _snapshot({
        id: 'fleet:service:svc-a',
        level: 'critical',
        scope: 'service',
        title: 'Service signal: svc-a',
        message: '3 failures across 3 runs',
        latest_run_id: 'run-focus-1',
        linkage: {
          replay: { run_id: 'run-focus-1', available: true },
          incidents: ['inc-1'],
          recommendations: ['rec-1'],
          evidence_refs: ['run:run-focus-1'],
        },
      }),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<FocusModePanel onOpenReplay={onOpenReplay} />)

    expect(screen.getByText('Service signal: svc-a: 3 failures across 3 runs')).toBeInTheDocument()
    expect(screen.getByText('run:run-focus-1')).toBeInTheDocument()
    expect(screen.getByText('Open replay and record outcome.')).toBeInTheDocument()
    expect(screen.getByText('Record outcome')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Replay run-focus/i }))

    expect(onOpenReplay).toHaveBeenCalledWith('run-focus-1')
  })

  it('renders recurrence when no fleet signal exists', async () => {
    const user = userEvent.setup()
    const onOpenReplay = vi.fn()
    mockUseApiFetch.mockReturnValue({
      data: _snapshot(null, recurrence),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<FocusModePanel onOpenReplay={onOpenReplay} />)

    expect(screen.getAllByText('service:svc-focus').length).toBeGreaterThan(0)
    expect(screen.getByText('1 recurring pattern(s).')).toBeInTheDocument()
    expect(screen.getByText('Top recurrence')).toBeInTheDocument()
    expect(screen.getByText('Evidence refs: run:fr2, run:fr1')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Replay fr2/i }))

    expect(onOpenReplay).toHaveBeenCalledWith('fr2')
  })

  it('routes evidence button to artifacts', async () => {
    const user = userEvent.setup()
    const onSelectTab = vi.fn()
    mockUseApiFetch.mockReturnValue({
      data: _snapshot(),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<FocusModePanel onSelectTab={onSelectTab} />)

    await user.click(screen.getByRole('button', { name: 'Evidence' }))

    expect(onSelectTab).toHaveBeenCalledWith('artifacts')
  })
})
