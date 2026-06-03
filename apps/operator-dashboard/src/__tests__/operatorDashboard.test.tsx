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
import { RuntimeHealthPanel } from '../mission-control/components/RuntimeHealthPanel'
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

// ── Regression: React key prop on conditional list items ──────────────────
/**
 * Every <li> rendered inside a .map() or conditional block inside a <ul>
 * must carry a stable key prop. React warns (console.error) when a sibling
 * array element lacks a key. Empty-state conditionals are easy to miss
 * because they only render when the list is empty.
 */
describe('React key prop — empty-state list items', () => {
  const keyWarning = /Warning: Each child in a list should have a unique "key" prop/

  function assertNoKeyWarning<T>(renderFn: () => T): T {
    const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
    try {
      const result = renderFn()
      const keyCalls = spy.mock.calls.filter((call) =>
        call.some((arg) => typeof arg === 'string' && keyWarning.test(arg))
      )
      expect(keyCalls).toHaveLength(0)
      return result
    } finally {
      spy.mockRestore()
    }
  }

  it('TopologyGraph: no key warning when circuits are empty', () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({ status: 'ok', circuits: {} })
    assertNoKeyWarning(() => render(<TopologyGraph />))
  })

  it('ArtifactBrowser: no key warning when records are empty', () => {
    vi.mocked(api.listRuns).mockResolvedValue([])
    assertNoKeyWarning(() => render(<ArtifactBrowser />))
  })

  it('ReplayExplorer: no key warning when runs are empty', () => {
    vi.mocked(api.listRuns).mockResolvedValue([])
    assertNoKeyWarning(() => render(<ReplayExplorer />))
  })

  it('RuntimeTimeline: no key warning when runs are empty', () => {
    vi.mocked(api.listRuns).mockResolvedValue([])
    assertNoKeyWarning(() => render(<RuntimeTimeline />))
  })
})

// ── A11y: button type="button" ───────────────────────────────────────────
describe('A11y — buttons have explicit type="button"', () => {
  it('App: tab buttons have type="button"', () => {
    render(<App />)
    const tabs = screen.getAllByRole('tab')
    for (const tab of tabs) {
      expect(tab.getAttribute('type')).toBe('button')
    }
  })

  it('ArtifactBrowser: filter buttons have type="button"', async () => {
    render(<ArtifactBrowser />)
    await waitFor(() => screen.getByRole('button', { name: /^all/i }))
    const filterBtns = screen.getAllByRole('button').filter(
      (b: HTMLElement) => b.hasAttribute('aria-pressed'),
    )
    for (const btn of filterBtns) {
      expect(btn.getAttribute('type')).toBe('button')
    }
  })

  it('ReplayExplorer: copy button has type="button"', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([fakeRun('run-btn-type', 'completed') as never])
    render(<ReplayExplorer />)
    await waitFor(() => screen.getByTitle('Copy run ID'))
    expect(screen.getByTitle('Copy run ID').getAttribute('type')).toBe('button')
  })

  it('TopologyGraph: reset button has type="button"', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      circuits: { 'svc.a': { state: 'open', failures: 1 } },
    } as never)
    render(<TopologyGraph />)
    await waitFor(() => screen.getByRole('button', { name: /reset/i }))
    expect(screen.getByRole('button', { name: /reset/i }).getAttribute('type')).toBe('button')
  })
})

// ── A11y: decorative dots hidden from assistive tech ──────────────────────
describe('A11y — decorative dots have aria-hidden="true"', () => {
  it('TopologyGraph: status dot is aria-hidden', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      circuits: { 'svc.b': { state: 'closed', failures: 0 } },
    } as never)
    render(<TopologyGraph />)
    await waitFor(() => document.querySelector('.mc-dot'))
    const dot = document.querySelector('.mc-dot')
    expect(dot).not.toBeNull()
    expect(dot!.getAttribute('aria-hidden')).toBe('true')
  })

  it('ArtifactBrowser: status dot is aria-hidden', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([fakeRun('run-dot', 'completed') as never])
    render(<ArtifactBrowser />)
    await waitFor(() => document.querySelector('.mc-dot'))
    const dot = document.querySelector('.mc-dot')
    expect(dot).not.toBeNull()
    expect(dot!.getAttribute('aria-hidden')).toBe('true')
  })

  it('ReplayExplorer: status dot is aria-hidden', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([fakeRun('run-dot2', 'failed') as never])
    render(<ReplayExplorer />)
    await waitFor(() => document.querySelector('.mc-dot'))
    const dot = document.querySelector('.mc-dot')
    expect(dot).not.toBeNull()
    expect(dot!.getAttribute('aria-hidden')).toBe('true')
  })

  it('RuntimeTimeline: status dot is aria-hidden', async () => {
    vi.mocked(api.listRuns).mockResolvedValue([fakeRun('run-dot3', 'pending') as never])
    render(<RuntimeTimeline />)
    await waitFor(() => document.querySelector('.mc-dot'))
    const dot = document.querySelector('.mc-dot')
    expect(dot).not.toBeNull()
    expect(dot!.getAttribute('aria-hidden')).toBe('true')
  })
})

// ── A11y: polling summaries have aria-live="polite" ───────────────────────
describe('A11y — polling status summaries have aria-live="polite"', () => {
  it('TopologyGraph: open circuit summary is aria-live', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      circuits: { 'svc.c': { state: 'closed', failures: 0 } },
    } as never)
    render(<TopologyGraph />)
    await waitFor(() => screen.getByText('All closed'))
    expect(screen.getByText('All closed').getAttribute('aria-live')).toBe('polite')
  })

  it('ArtifactBrowser: record count is aria-live', async () => {
    render(<ArtifactBrowser />)
    await waitFor(() => screen.getByText(/records/))
    expect(screen.getByText(/records/).getAttribute('aria-live')).toBe('polite')
  })

  it('ReplayExplorer: run count is aria-live', async () => {
    render(<ReplayExplorer />)
    await waitFor(() => screen.getByText(/runs/))
    expect(screen.getByText(/runs/).getAttribute('aria-live')).toBe('polite')
  })

  it('RuntimeTimeline: run count is aria-live', async () => {
    render(<RuntimeTimeline />)
    await waitFor(() => screen.getByText(/runs/))
    expect(screen.getByText(/runs/).getAttribute('aria-live')).toBe('polite')
  })

  it('RuntimeHealthPanel: health status is aria-live', async () => {
    render(<RuntimeHealthPanel />)
    await waitFor(() => screen.getByText(/Healthy|Attention/))
    expect(screen.getByText(/Healthy|Attention/).getAttribute('aria-live')).toBe('polite')
  })
})
