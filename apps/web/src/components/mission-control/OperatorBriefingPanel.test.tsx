import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { OperatorBriefingPanel } from './OperatorBriefingPanel'

const mockUseApiFetch = vi.fn()

vi.mock('../../hooks/useApiFetch', () => ({
  useApiFetch: (...args: unknown[]) => mockUseApiFetch(...args),
}))

function _missionControl(topSignal: Record<string, unknown> | null = null) {
  return {
    fleet_summary: {
      status: topSignal ? 'critical' : 'nominal',
      active_signals: topSignal ? 1 : 0,
      critical_signals: topSignal ? 1 : 0,
      warning_signals: 0,
      top_signal: topSignal,
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

describe('OperatorBriefingPanel', () => {
  it('renders a nominal briefing from Mission Control', () => {
    mockUseApiFetch.mockReturnValue({
      data: _missionControl(),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OperatorBriefingPanel />)

    expect(screen.getByText('Operator Briefing')).toBeInTheDocument()
    expect(screen.getByText('NOMINAL')).toBeInTheDocument()
    expect(screen.getByText('No interrupting fleet signal. Monitor fleet health.')).toBeInTheDocument()
  })

  it('renders top signal linkage and opens replay', async () => {
    const user = userEvent.setup()
    const onOpenReplay = vi.fn()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl({
        id: 'fleet:service:svc-a',
        level: 'critical',
        scope: 'service',
        title: 'Service signal: svc-a',
        message: '3 failures across 3 runs',
        latest_run_id: 'run-1',
        linkage: {
          replay: { run_id: 'run-1', available: true },
          incidents: ['inc-1'],
          recommendations: ['rec-1'],
          evidence_refs: ['run:run-1'],
        },
      }),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OperatorBriefingPanel onOpenReplay={onOpenReplay} />)

    expect(screen.getByText('CRITICAL')).toBeInTheDocument()
    expect(screen.getByText('Service signal: svc-a')).toBeInTheDocument()
    expect(screen.getByText('3 failures across 3 runs')).toBeInTheDocument()
    expect(screen.getByText('Incidents: inc-1')).toBeInTheDocument()
    expect(screen.getByText('Recommendations: rec-1')).toBeInTheDocument()
    expect(screen.getByText('Evidence refs: run:run-1')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Replay run-1/i }))

    expect(onOpenReplay).toHaveBeenCalledWith('run-1')
  })

  it('routes evidence action to artifacts tab', async () => {
    const user = userEvent.setup()
    const onSelectTab = vi.fn()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl({
        id: 'fleet:service:svc-a',
        level: 'warning',
        scope: 'service',
        title: 'Service signal: svc-a',
        message: '1 failure across 1 run',
        latest_run_id: 'run-2',
        linkage: { replay: { run_id: 'run-2', available: true } },
      }),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OperatorBriefingPanel onSelectTab={onSelectTab} />)

    await user.click(screen.getByRole('button', { name: 'Evidence' }))

    expect(onSelectTab).toHaveBeenCalledWith('artifacts')
  })
})
