import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { OperatorBriefingPanel } from './OperatorBriefingPanel'

const mockUseApiFetch = vi.fn()

vi.mock('../../hooks/useApiFetch', () => ({
  useApiFetch: (...args: unknown[]) => mockUseApiFetch(...args),
}))

function _missionControl(topSignal: Record<string, unknown> | null = null, incidentSummary: Record<string, unknown> | null = null) {
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
    id: 'incident:service:svc-a',
    scope: 'service',
    value: 'svc-a',
    recurrence_count: 2,
    affected_run_ids: ['ir2', 'ir1'],
    latest_run_id: 'ir2',
    linked_incident_ids: ['inc-r'],
    linked_recommendation_ids: ['rec-r'],
    evidence_refs: ['run:ir2', 'run:ir1'],
  },
}

beforeEach(() => {
  mockUseApiFetch.mockReset()
  vi.stubGlobal('fetch', vi.fn().mockResolvedValue({
    ok: true,
    json: vi.fn().mockResolvedValue({ status: 'ok' }),
  }))
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
    expect(screen.getByText('Monitor fleet health. No operator action required.')).toBeInTheDocument()
    expect(screen.getByText('No interrupting fleet signal. Monitor fleet health.')).toBeInTheDocument()
    expect(screen.queryByText('Record outcome')).not.toBeInTheDocument()
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
    expect(screen.getByText('Open replay, inspect evidence, then record recommendation outcome.')).toBeInTheDocument()
    expect(screen.getByText('Linked context: replay run-1 · 1 recommendation(s) · 1 incident(s) · 1 evidence ref(s).')).toBeInTheDocument()
    expect(screen.getByText('Service signal: svc-a')).toBeInTheDocument()
    expect(screen.getByText('3 failures across 3 runs')).toBeInTheDocument()
    expect(screen.getByText('Incidents: inc-1')).toBeInTheDocument()
    expect(screen.getByText('Recommendations: rec-1')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'run:run-1' })).toBeInTheDocument()
    expect(screen.getByText('Record outcome')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Replay run-1/i }))

    expect(onOpenReplay).toHaveBeenCalledWith('run-1', ['rec-1'])
  })

  it('surfaces top recurrence and opens replay', async () => {
    const user = userEvent.setup()
    const onOpenReplay = vi.fn()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl(null, recurrence),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OperatorBriefingPanel onOpenReplay={onOpenReplay} />)

    expect(screen.getByText('Top recurrence')).toBeInTheDocument()
    expect(screen.getByText('service:svc-a')).toBeInTheDocument()
    expect(screen.getByText('2 recurring failure(s) across 2 run(s).')).toBeInTheDocument()
    expect(screen.getByText('Evidence refs: run:ir2, run:ir1')).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: /Replay ir2/i }))

    expect(onOpenReplay).toHaveBeenCalledWith('ir2')
  })

  it('routes evidence action to the first linked evidence ref', async () => {
    const user = userEvent.setup()
    const onOpenEvidence = vi.fn()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl({
        id: 'fleet:service:svc-a',
        level: 'warning',
        scope: 'service',
        title: 'Service signal: svc-a',
        message: '1 failure across 1 run',
        latest_run_id: 'run-2',
        linkage: {
          replay: { run_id: 'run-2', available: true },
          evidence_refs: ['run:run-2'],
        },
      }),
      loading: false,
      error: null,
      refetch: vi.fn(),
    })

    render(<OperatorBriefingPanel onOpenEvidence={onOpenEvidence} />)

    await user.click(screen.getByRole('button', { name: 'Evidence' }))

    expect(onOpenEvidence).toHaveBeenCalledWith('run:run-2')
  })

  it('falls back to artifacts tab when no evidence ref exists', async () => {
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

  it('records a linked recommendation outcome and refreshes briefing', async () => {
    const user = userEvent.setup()
    const refetch = vi.fn()
    mockUseApiFetch.mockReturnValue({
      data: _missionControl({
        id: 'fleet:service:svc-a',
        level: 'critical',
        scope: 'service',
        title: 'Service signal: svc-a',
        message: '3 failures across 3 runs',
        latest_run_id: 'run-3',
        linkage: {
          replay: { run_id: 'run-3', available: true },
          recommendations: ['rec-3'],
        },
      }),
      loading: false,
      error: null,
      refetch,
    })

    render(<OperatorBriefingPanel />)

    await user.click(screen.getByRole('button', { name: 'Resolved' }))

    expect(fetch).toHaveBeenCalledWith(
      `${window.location.origin}/api/uar/recommendations/outcome`,
      expect.objectContaining({
        body: JSON.stringify({
          recommendation_id: 'rec-3',
          outcome_type: 'resolved',
          run_id: 'run-3',
          source: 'operator_briefing',
        }),
      })
    )
    expect(refetch).toHaveBeenCalled()
  })
})
