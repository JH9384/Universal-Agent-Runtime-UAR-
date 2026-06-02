/**
 * Operator Dashboard — structural & ARIA regression tests
 *
 * Covered:
 *  1. App.tsx         — aria-selected must be string "true"/"false", not boolean
 *  2. ArtifactBrowser — aria-pressed must be string "true"/"false"
 *  3. RuntimeTimeline — CSS classes used instead of inline layout styles
 *  4. TopologyGraph   — conditional summary CSS classes
 *  5. ReplayExplorer  — copyId .catch() prevents silent clipboard failure
 */

import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { App } from '../App'
import { ArtifactBrowser } from '../mission-control/components/ArtifactBrowser'
import { ReplayExplorer } from '../mission-control/components/ReplayExplorer'
import { RuntimeTimeline } from '../mission-control/components/RuntimeTimeline'
import { TopologyGraph } from '../mission-control/components/TopologyGraph'

// ── mock the api client ────────────────────────────────────────────────────
vi.mock('../api/client', () => ({
  api: {
    listRuns: vi.fn().mockResolvedValue([]),
    circuitBreakers: vi.fn().mockResolvedValue({ circuits: {} }),
    resetCircuitBreaker: vi.fn().mockResolvedValue({}),
    healthDashboard: vi.fn().mockResolvedValue({
      active_runs: 0,
      total_skills: 0,
      cache_hit_rate: 0,
      error_rate: 0,
      uptime_seconds: 0,
    }),
  },
}))

import { api } from '../api/client'

afterEach(() => vi.clearAllMocks())

// ── helpers ────────────────────────────────────────────────────────────────
const fakeRun = (id = 'run-abc-123456', status = 'completed') => ({
  run_id: id,
  status,
  skills: [],
  created_at: Date.now(),
})

// ── App — aria-selected ────────────────────────────────────────────────────
describe('App — aria-selected on tab buttons', () => {
  it('sets aria-selected="true" (string) on the active tab', () => {
    render(<App />)
    expect(screen.getByRole('tab', { name: /Health/i }).getAttribute('aria-selected')).toBe('true')
  })

  it('sets aria-selected="false" (string) on inactive tabs', () => {
    render(<App />)
    expect(screen.getByRole('tab', { name: /Replay/i }).getAttribute('aria-selected')).toBe('false')
  })

  it('updates aria-selected when a different tab is clicked', () => {
    render(<App />)
    const replayTab = screen.getByRole('tab', { name: /Replay/i })
    const healthTab = screen.getByRole('tab', { name: /Health/i })
    fireEvent.click(replayTab)
    expect(replayTab.getAttribute('aria-selected')).toBe('true')
    expect(healthTab.getAttribute('aria-selected')).toBe('false')
  })

  it('regression: boolean aria-selected is invalid ARIA — must be the string "true"/"false"', () => {
    // ARIA spec §6.6: aria-selected = "true" | "false" | "undefined"
    // React renders boolean true as aria-selected="" in some serialisers — invalid.
    render(<App />)
    const tabs = screen.getAllByRole('tab')
    for (const tab of tabs) {
      const val = tab.getAttribute('aria-selected')
      expect(['true', 'false']).toContain(val)
    }
  })
})

// ── ArtifactBrowser — aria-pressed ────────────────────────────────────────
describe('ArtifactBrowser — aria-pressed on filter buttons', () => {
  it('sets aria-pressed="true" (string) on the active filter', async () => {
    render(<ArtifactBrowser />)
    await waitFor(() => screen.getByRole('button', { name: /^all/i }))
    expect(screen.getByRole('button', { name: /^all/i }).getAttribute('aria-pressed')).toBe('true')
  })

  it('sets aria-pressed="false" (string) on inactive filters', async () => {
    render(<ArtifactBrowser />)
    await waitFor(() => screen.getByRole('button', { name: /completed/i }))
    expect(screen.getByRole('button', { name: /completed/i }).getAttribute('aria-pressed')).toBe('false')
  })

  it('switches aria-pressed when a filter is clicked', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([fakeRun('run-001', 'completed') as never])
    render(<ArtifactBrowser />)
    await waitFor(() => screen.getByRole('button', { name: /completed/i }))
    fireEvent.click(screen.getByRole('button', { name: /completed/i }))
    expect(screen.getByRole('button', { name: /completed/i }).getAttribute('aria-pressed')).toBe('true')
    expect(screen.getByRole('button', { name: /^all/i }).getAttribute('aria-pressed')).toBe('false')
  })

  it('regression: all filter button aria-pressed values must be strings', async () => {
    render(<ArtifactBrowser />)
    await waitFor(() => screen.getByRole('button', { name: /^all/i }))
    const filterBtns = screen.getAllByRole('button').filter(
      (b: HTMLElement) => b.hasAttribute('aria-pressed'),
    )
    expect(filterBtns.length).toBeGreaterThan(0)
    for (const btn of filterBtns) {
      expect(['true', 'false']).toContain(btn.getAttribute('aria-pressed'))
    }
  })
})

// ── RuntimeTimeline — CSS classes ─────────────────────────────────────────
describe('RuntimeTimeline — uses CSS classes instead of inline layout styles', () => {
  beforeEach(() => {
    vi.mocked(api.listRuns).mockResolvedValue([fakeRun() as never])
  })

  it('renders list items with mc-row class', async () => {
    render(<RuntimeTimeline />)
    await waitFor(() => document.querySelector('li.mc-row'))
    expect(document.querySelector('li.mc-row')).not.toBeNull()
  })

  it('renders status dot with mc-dot class', async () => {
    render(<RuntimeTimeline />)
    await waitFor(() => document.querySelector('.mc-dot'))
    expect(document.querySelector('.mc-dot')).not.toBeNull()
  })

  it('renders status badge with mc-status-badge class', async () => {
    render(<RuntimeTimeline />)
    await waitFor(() => screen.getByText(/completed/i))
    expect(document.querySelector('.mc-status-badge')).not.toBeNull()
  })

  it('run ID code has mc-run-id class', async () => {
    render(<RuntimeTimeline />)
    await waitFor(() => document.querySelector('.mc-run-id'))
    expect(document.querySelector('.mc-run-id')).not.toBeNull()
  })

  it('shows empty state with mc-meta--muted class when no runs', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([])
    render(<RuntimeTimeline />)
    await waitFor(() => screen.getByText(/No runs yet/i))
    expect(screen.getByText(/No runs yet/i).className).toContain('mc-meta--muted')
  })
})

// ── TopologyGraph — conditional CSS classes ───────────────────────────────
describe('TopologyGraph — conditional summary classes', () => {
  it('uses mc-status-summary--ok when no circuits are open', async () => {
    render(<TopologyGraph />)
    await waitFor(() => screen.getByText('All closed'))
    expect(screen.getByText('All closed').className).toContain('mc-status-summary--ok')
  })

  it('uses mc-status-summary--warn when a circuit is open', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      circuits: { 'skill.run': { state: 'open', failures: 3 } },
    } as never)
    render(<TopologyGraph />)
    await waitFor(() => screen.getByText(/1 open/i))
    expect(screen.getByText(/1 open/i).className).toContain('mc-status-summary--warn')
  })

  it('renders Reset button with mc-reset-btn class', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      circuits: { 'skill.run': { state: 'open', failures: 2 } },
    } as never)
    render(<TopologyGraph />)
    await waitFor(() => screen.getByRole('button', { name: /reset/i }))
    expect(screen.getByRole('button', { name: /reset/i }).className).toContain('mc-reset-btn')
  })

  it('mc-subtext class used on circuit name', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      circuits: { 'my.circuit': { state: 'closed', failures: 0 } },
    } as never)
    render(<TopologyGraph />)
    await waitFor(() => screen.getByText('my.circuit'))
    expect(screen.getByText('my.circuit').className).toContain('mc-subtext')
  })

  it('failure count has mc-meta--warn class', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      circuits: { 'skill.run': { state: 'open', failures: 5 } },
    } as never)
    render(<TopologyGraph />)
    await waitFor(() => screen.getByText(/5✗/))
    expect(screen.getByText(/5✗/).className).toContain('mc-meta--warn')
  })
})

// ── ReplayExplorer — copyId error handling ────────────────────────────────
describe('ReplayExplorer — copyId handles clipboard failure', () => {
  beforeEach(() => {
    vi.mocked(api.listRuns).mockResolvedValue([fakeRun('run-copy-test', 'completed') as never])
  })

  it('does not throw when clipboard.writeText rejects', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockRejectedValue(new Error('Permission denied')) },
      writable: true,
      configurable: true,
    })
    render(<ReplayExplorer />)
    await waitFor(() => screen.getByTitle('Copy run ID'))
    expect(() => fireEvent.click(screen.getByTitle('Copy run ID'))).not.toThrow()
  })

  it('shows checkmark on successful copy', async () => {
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue(undefined) },
      writable: true,
      configurable: true,
    })
    render(<ReplayExplorer />)
    await waitFor(() => screen.getByTitle('Copy run ID'))
    fireEvent.click(screen.getByTitle('Copy run ID'))
    await waitFor(() => screen.getByText('✓'))
    expect(screen.getByText('✓')).toBeInTheDocument()
  })

  it('regression: old copyId had no .catch() — clipboard rejection was unhandled', async () => {
    // Verify that the current implementation gracefully handles rejection
    const rejected = vi.fn().mockRejectedValue(new Error('blocked'))
    Object.defineProperty(navigator, 'clipboard', {
      value: { writeText: rejected },
      writable: true,
      configurable: true,
    })
    render(<ReplayExplorer />)
    await waitFor(() => screen.getByTitle('Copy run ID'))
    fireEvent.click(screen.getByTitle('Copy run ID'))
    // wait a tick to let the promise chain settle
    await new Promise((r) => setTimeout(r, 20))
    // component is still alive — no unhandled rejection crash
    expect(screen.getByTitle('Copy run ID')).toBeInTheDocument()
  })
})

// ── ReplayExplorer — search/filter ────────────────────────────────────────
describe('ReplayExplorer — filter input', () => {
  it('filters runs by run_id substring', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([
      fakeRun('run-aaa', 'completed') as never,
      fakeRun('run-bbb', 'failed') as never,
    ])
    render(<ReplayExplorer />)
    await waitFor(() => screen.getByText('run-aaa'))

    fireEvent.change(screen.getByPlaceholderText(/Filter/i), { target: { value: 'aaa' } })
    expect(screen.queryByText('run-aaa')).toBeInTheDocument()
    expect(screen.queryByText('run-bbb')).not.toBeInTheDocument()
  })

  it('shows mc-meta--muted empty state when no runs match filter', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([fakeRun('run-xyz', 'completed') as never])
    render(<ReplayExplorer />)
    await waitFor(() => screen.getByText('run-xyz'))

    fireEvent.change(screen.getByPlaceholderText(/Filter/i), { target: { value: 'zzznomatch' } })
    await waitFor(() => screen.getByText(/No matching runs/i))
    expect(screen.getByText(/No matching runs/i).className).toContain('mc-meta--muted')
  })
})
