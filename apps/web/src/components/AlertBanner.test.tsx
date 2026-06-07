import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AlertBanner } from './AlertBanner'

const mockUseApiFetch = vi.fn()

vi.mock('../hooks/useApiFetch', () => ({
  useApiFetch: (...args: unknown[]) => mockUseApiFetch(...args),
}))

function _alertsSummary(topAlert: Record<string, unknown>) {
  return {
    hours: 24,
    count: 1,
    top_alert: topAlert,
    alerts: [topAlert],
  }
}

function _missionControlFleet(level: 'critical' | 'warning' | 'info') {
  return {
    fleet_summary: {
      top_signal: {
        id: 'fleet:service:svc-a',
        level,
        scope: 'service',
        title: 'Service signal: svc-a',
        message: '3 failure(s), 0 warning(s) across 3 run(s)',
        latest_run_id: 'run-1',
      },
    },
  }
}

beforeEach(() => {
  mockUseApiFetch.mockReset()
  localStorage.clear()
})

describe('AlertBanner fleet surfacing', () => {
  it('shows a critical fleet signal ahead of an existing warning alert', () => {
    mockUseApiFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/uar/alerts/summary')) {
        return {
          data: _alertsSummary({
            level: 'warning',
            source: 'burnin',
            message: 'Burn-In not passed',
            tab: 'health',
          }),
          loading: false,
          error: null,
        }
      }
      if (url === '/api/uar/mission-control') {
        return {
          data: _missionControlFleet('critical'),
          loading: false,
          error: null,
        }
      }
      return { data: null, loading: false, error: null }
    })

    render(<AlertBanner />)

    expect(screen.getByRole('alert')).toHaveTextContent('Service signal: svc-a')
    expect(screen.getByRole('alert')).toHaveTextContent('3 failure')
  })

  it('keeps the existing critical API alert ahead of a warning fleet signal', () => {
    mockUseApiFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/uar/alerts/summary')) {
        return {
          data: _alertsSummary({
            level: 'critical',
            source: 'certification',
            message: 'Certification score collapsed to 20',
            tab: 'health',
          }),
          loading: false,
          error: null,
        }
      }
      if (url === '/api/uar/mission-control') {
        return {
          data: _missionControlFleet('warning'),
          loading: false,
          error: null,
        }
      }
      return { data: null, loading: false, error: null }
    })

    render(<AlertBanner />)

    expect(screen.getByRole('alert')).toHaveTextContent('Certification score collapsed')
    expect(screen.getByRole('alert')).not.toHaveTextContent('Service signal')
  })

  it('opens Mission Control health tab when clicking a fleet alert', async () => {
    const user = userEvent.setup()
    const onOpenMissionControl = vi.fn()
    mockUseApiFetch.mockImplementation((url: string) => {
      if (url.startsWith('/api/uar/alerts/summary')) {
        return {
          data: _alertsSummary({
            level: 'info',
            source: 'system',
            message: 'All systems nominal',
            tab: 'health',
          }),
          loading: false,
          error: null,
        }
      }
      if (url === '/api/uar/mission-control') {
        return {
          data: _missionControlFleet('critical'),
          loading: false,
          error: null,
        }
      }
      return { data: null, loading: false, error: null }
    })

    render(<AlertBanner onOpenMissionControl={onOpenMissionControl} />)

    await user.click(screen.getByRole('alert'))

    expect(onOpenMissionControl).toHaveBeenCalledWith('health')
  })
})
