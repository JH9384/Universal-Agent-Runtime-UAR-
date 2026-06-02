/**
 * ARIA attribute string-value regression tests
 *
 * ARIA spec §6.6 requires aria-selected / aria-pressed / aria-expanded to be
 * the *string* "true" or "false", not a JS boolean.  React renders a boolean
 * true as the empty-string attribute (aria-selected="") in some runtimes, and
 * omits it entirely for false — both are invalid and confuse screen readers.
 *
 * Covered components:
 *   - CollapsibleSection  — aria-expanded boolean → string
 *   - SkillSelector       — aria-expanded boolean → string
 *   - SettingsDrawer      — aria-pressed  boolean → string
 *   - IncidentWorkbench   — onStatusChange error handling + handleSubmit !res.ok
 */

import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import CollapsibleSection from '../CollapsibleSection'
import SkillSelector from '../SkillSelector'
import SettingsDrawer from '../SettingsDrawer'
import { IncidentWorkbench } from '../IncidentWorkbench'

afterEach(() => vi.restoreAllMocks())

// ── CollapsibleSection — aria-expanded ────────────────────────────────────
describe('CollapsibleSection — aria-expanded', () => {
  it('is the string "true" when expanded (defaultOpen=true)', () => {
    render(
      <CollapsibleSection id="test-open" title="Open Section">
        <span>content</span>
      </CollapsibleSection>,
    )
    const header = screen.getByRole('button', { name: /Open Section/i })
    expect(header.getAttribute('aria-expanded')).toBe('true')
  })

  it('is the string "false" when collapsed (defaultOpen=false)', () => {
    render(
      <CollapsibleSection id="test-closed" title="Closed Section" defaultOpen={false}>
        <span>content</span>
      </CollapsibleSection>,
    )
    const header = screen.getByRole('button', { name: /Closed Section/i })
    expect(header.getAttribute('aria-expanded')).toBe('false')
  })

  it('toggles from "true" to "false" on click', () => {
    render(
      <CollapsibleSection id="test-toggle" title="Toggle Section">
        <span>content</span>
      </CollapsibleSection>,
    )
    const header = screen.getByRole('button', { name: /Toggle Section/i })
    expect(header.getAttribute('aria-expanded')).toBe('true')
    fireEvent.click(header)
    expect(header.getAttribute('aria-expanded')).toBe('false')
  })

  it('regression: aria-expanded must never be empty string or absent', () => {
    render(
      <CollapsibleSection id="test-reg" title="Reg Section">
        <span>x</span>
      </CollapsibleSection>,
    )
    const val = screen.getByRole('button').getAttribute('aria-expanded')
    expect(val).not.toBe('')
    expect(val).not.toBeNull()
    expect(['true', 'false']).toContain(val)
  })
})

// ── SkillSelector — aria-expanded on group headers ────────────────────────
describe('SkillSelector — aria-expanded on skill group headers', () => {
  const baseProps = {
    skillSearch: '',
    debouncedSkillSearch: '',
    onSkillSearchChange: vi.fn(),
    skillsDisplayMode: 'dropdown' as const,
    onToggleDisplayMode: vi.fn(),
    onToggleGroup: vi.fn(),
    unifiedOrder: [],
    onAddSkill: vi.fn(),
    isRunning: false,
    skillGroups: [
      {
        name: 'Core',
        icon: '⚙',
        skills: [{ id: 'skill.run', label: 'Run', desc: 'Run a task' }],
      },
    ],
    availableSkills: [{ id: 'skill.run', label: 'Run', desc: 'Run a task' }],
    badges: {},
    stubDeps: {},
  }

  function getGroupHeader(container: HTMLElement) {
    // Group header is a div[role="button"] with aria-expanded (list display mode)
    return (
      container.querySelector('div[role="button"][aria-expanded]') as HTMLElement | null
    )
  }

  it('is the string "true" when group is expanded', () => {
    const { container } = render(<SkillSelector {...baseProps} collapsedGroups={{}} />)
    expect(getGroupHeader(container)?.getAttribute('aria-expanded')).toBe('true')
  })

  it('is the string "false" when group is collapsed', () => {
    const { container } = render(<SkillSelector {...baseProps} collapsedGroups={{ Core: true }} />)
    expect(getGroupHeader(container)?.getAttribute('aria-expanded')).toBe('false')
  })

  it('regression: aria-expanded must be a string not boolean', () => {
    const { container } = render(<SkillSelector {...baseProps} collapsedGroups={{}} />)
    const val = getGroupHeader(container)?.getAttribute('aria-expanded')
    expect(['true', 'false']).toContain(val)
  })
})

// ── SettingsDrawer — aria-pressed on mode cards ───────────────────────────
describe('SettingsDrawer — aria-pressed on deployment mode buttons', () => {
  const noop = vi.fn()
  const baseProps = {
    open: true,
    onClose: noop,
    onDeploymentModeChange: noop,
    apiKey: '',
    onApiKeyChange: noop,
    ollamaModel: '',
    onOllamaModelChange: noop,
    useHierarchical: false,
    onHierarchicalChange: noop,
    useWebSocket: false,
    onUseWebSocketChange: noop,
    graphragMethod: 'local' as const,
    onGraphragMethodChange: noop,
    autonomiKey: '',
    onAutonomiKeyChange: noop,
    autonomiNetwork: 'testnet' as const,
    onAutonomiNetworkChange: noop,
    autonomiPublic: false,
    onAutonomiPublicChange: noop,
    autonomiAddress: '',
    onAutonomiAddressChange: noop,
  }

  function getModeButtons(container: HTMLElement) {
    return Array.from(container.querySelectorAll('button[aria-pressed]')) as HTMLElement[]
  }

  it('first mode button (Local) has aria-pressed="true" when mode is local', () => {
    const { container } = render(<SettingsDrawer {...baseProps} deploymentMode="local" />)
    const [localBtn, sharedBtn] = getModeButtons(container)
    expect(localBtn.getAttribute('aria-pressed')).toBe('true')
    expect(sharedBtn.getAttribute('aria-pressed')).toBe('false')
  })

  it('second mode button (Shared) has aria-pressed="true" when mode is shared', () => {
    const { container } = render(<SettingsDrawer {...baseProps} deploymentMode="shared" />)
    const [localBtn, sharedBtn] = getModeButtons(container)
    expect(sharedBtn.getAttribute('aria-pressed')).toBe('true')
    expect(localBtn.getAttribute('aria-pressed')).toBe('false')
  })

  it('regression: aria-pressed must never be empty string', () => {
    render(<SettingsDrawer {...baseProps} deploymentMode="local" />)
    const modeBtns = screen
      .getAllByRole('button')
      .filter((b: HTMLElement) => b.hasAttribute('aria-pressed'))
    expect(modeBtns.length).toBeGreaterThan(0)
    for (const btn of modeBtns) {
      expect(['true', 'false']).toContain(btn.getAttribute('aria-pressed'))
    }
  })
})

// ── IncidentWorkbench — onStatusChange error handling ─────────────────────
describe('IncidentWorkbench — onStatusChange error handling', () => {
  const fakeIncident = {
    id: 'inc-1',
    title: 'DB spike',
    description: '',
    status: 'open',
    severity: 'high',
    linked_run_ids: [],
    linked_rec_ids: [],
    resolution_notes: '',
    created_at: 0,
    updated_at: 0,
  }

  it('shows error banner when PUT returns non-ok status', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [fakeIncident] })  // GET
      .mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({}) }) // PUT

    render(<IncidentWorkbench />)
    await waitFor(() => screen.getByText('DB spike'))

    fireEvent.click(screen.getByRole('button', { name: /Mark Resolved/i }))

    await waitFor(() =>
      expect(screen.getByText(/Status update failed: 503/i)).toBeInTheDocument(),
    )
  })

  it('shows error banner on network error during status change', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [fakeIncident] })
      .mockRejectedValueOnce(new Error('Network down'))

    render(<IncidentWorkbench />)
    await waitFor(() => screen.getByText('DB spike'))

    fireEvent.click(screen.getByRole('button', { name: /Mark Resolved/i }))

    await waitFor(() =>
      expect(screen.getByText(/Network down/i)).toBeInTheDocument(),
    )
  })
})

// ── IncidentWorkbench — handleSubmit !res.ok ──────────────────────────────
describe('IncidentWorkbench — IncidentForm save error handling', () => {
  it('shows saveError banner when POST returns non-ok status', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })  // GET list
      .mockResolvedValueOnce({ ok: false, status: 422, json: async () => ({}) }) // POST

    render(<IncidentWorkbench />)
    await waitFor(() => screen.getByRole('button', { name: /\+ New Incident/i }))

    fireEvent.click(screen.getByRole('button', { name: /\+ New Incident/i }))
    await waitFor(() => screen.getByPlaceholderText(/Title/i))

    fireEvent.change(screen.getByPlaceholderText(/Title \*/i), {
      target: { value: 'Test incident' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }))

    await waitFor(() =>
      expect(screen.getByText(/Save failed: 422/i)).toBeInTheDocument(),
    )
  })

  it('shows saveError banner on network error during save', async () => {
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockRejectedValueOnce(new Error('Offline'))

    render(<IncidentWorkbench />)
    await waitFor(() => screen.getByRole('button', { name: /\+ New Incident/i }))

    fireEvent.click(screen.getByRole('button', { name: /\+ New Incident/i }))
    await waitFor(() => screen.getByPlaceholderText(/Title/i))

    fireEvent.change(screen.getByPlaceholderText(/Title \*/i), {
      target: { value: 'Test incident' },
    })
    fireEvent.click(screen.getByRole('button', { name: /^Save$/i }))

    await waitFor(() =>
      expect(screen.getByText(/Offline/i)).toBeInTheDocument(),
    )
  })
})
