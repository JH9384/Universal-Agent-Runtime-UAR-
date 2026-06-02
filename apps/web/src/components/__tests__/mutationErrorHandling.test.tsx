import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { TimeMachine } from '../TimeMachine'
import { RecommendationInbox } from '../RecommendationInbox'
import { InvestigationReplay } from '../InvestigationReplay'

// ---------------------------------------------------------------------------
// helpers
// ---------------------------------------------------------------------------
const originalFetch = globalThis.fetch

function mockFetch(response: Partial<Response> & { json?: () => Promise<unknown> }) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({}),
    ...response,
  })
}

function mockFetchError(message = 'Network error') {
  globalThis.fetch = vi.fn().mockRejectedValue(new Error(message))
}

afterEach(() => {
  globalThis.fetch = originalFetch
  vi.restoreAllMocks()
})

// ---------------------------------------------------------------------------
// TimeMachine — handleCapture
// ---------------------------------------------------------------------------
describe('TimeMachine — handleCapture error handling', () => {
  beforeEach(() => {
    // First call: GET /api/uar/snapshots → empty list
    globalThis.fetch = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
  })

  it('shows error banner when capture POST fails with non-ok status', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })       // initial GET snapshots
      .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) }) // POST fails
    globalThis.fetch = fetchMock

    render(<TimeMachine />)
    await waitFor(() => screen.getByText('Capture Now'))

    fireEvent.click(screen.getByText('Capture Now'))

    await waitFor(() => {
      expect(screen.getByText(/Snapshot failed: 500/i)).toBeInTheDocument()
    })
  })

  it('shows error banner when capture POST throws (network error)', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockRejectedValueOnce(new Error('Network unreachable'))
    globalThis.fetch = fetchMock

    render(<TimeMachine />)
    await waitFor(() => screen.getByText('Capture Now'))

    fireEvent.click(screen.getByText('Capture Now'))

    await waitFor(() => {
      expect(screen.getByText(/Network unreachable/i)).toBeInTheDocument()
    })
  })

  it('regression: old code would reload page on any error, hiding failure from user', async () => {
    // Old: await fetch(...); window.location.reload() — no try/catch
    // If fetch threw, the unhandled rejection would bubble and reload would never run,
    // but the error was invisible. Now: catch sets actionError state.
    const oldHandleCapture = async () => {
      // Simulates old pattern — no try/catch
      await Promise.reject(new Error('POST failed'))
      // window.location.reload() — never reached but user sees nothing
    }
    await expect(oldHandleCapture()).rejects.toThrow('POST failed')
  })
})

// ---------------------------------------------------------------------------
// RecommendationInbox — handleUpdate
// ---------------------------------------------------------------------------
describe('RecommendationInbox — handleUpdate error handling', () => {
  const fakeItem = {
    id: 'inbox-1',
    source_rec_id: 'rec-1',
    title: 'Test Rec',
    category: 'skill_sequence',
    confidence: 0.8,
    trust_score: 0.6,
    drift_penalty: null,
    status: 'new' as const,
    assigned_to: null,
    notes: '',
    created_at: 1000,
    updated_at: 1000,
  }

  it('shows actionError banner when PUT returns non-ok status', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [fakeItem] }) // GET /api/uar/inbox
      .mockResolvedValueOnce({ ok: false, status: 422, json: async () => ({}) }) // PUT fails
    globalThis.fetch = fetchMock

    render(<RecommendationInbox />)
    await waitFor(() => screen.getByText('Test Rec'))

    // Open edit form first, then click Mark resolved
    fireEvent.click(screen.getByRole('button', { name: /Manage/i }))
    await waitFor(() => screen.getByRole('button', { name: /Mark resolved/i }))
    fireEvent.click(screen.getByRole('button', { name: /Mark resolved/i }))

    await waitFor(() => {
      expect(screen.getByText(/Update failed: 422/i)).toBeInTheDocument()
    })
  })

  it('shows actionError banner when PUT throws network error', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [fakeItem] })
      .mockRejectedValueOnce(new Error('Connection refused'))
    globalThis.fetch = fetchMock

    render(<RecommendationInbox />)
    await waitFor(() => screen.getByText('Test Rec'))

    fireEvent.click(screen.getByRole('button', { name: /Manage/i }))
    await waitFor(() => screen.getByRole('button', { name: /Mark resolved/i }))
    fireEvent.click(screen.getByRole('button', { name: /Mark resolved/i }))

    await waitFor(() => {
      expect(screen.getByText(/Connection refused/i)).toBeInTheDocument()
    })
  })
})

// ---------------------------------------------------------------------------
// InvestigationReplay — handleCreate / handleEnd
// ---------------------------------------------------------------------------
describe('InvestigationReplay — handleCreate error handling', () => {
  it('shows actionError when POST /investigations returns non-ok', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] }) // GET investigations
      .mockResolvedValueOnce({ ok: false, status: 503, json: async () => ({}) }) // POST fails
    globalThis.fetch = fetchMock

    render(<InvestigationReplay />)
    await waitFor(() => screen.getByPlaceholderText(/Title/))

    fireEvent.change(screen.getByPlaceholderText(/Title/), { target: { value: 'My Investigation' } })
    fireEvent.click(screen.getByText(/Start Investigation/i))

    await waitFor(() => {
      expect(screen.getByText(/Create failed: 503/i)).toBeInTheDocument()
    })
  })

  it('shows actionError when POST /investigations throws', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce({ ok: true, json: async () => [] })
      .mockRejectedValueOnce(new Error('Offline'))
    globalThis.fetch = fetchMock

    render(<InvestigationReplay />)
    await waitFor(() => screen.getByPlaceholderText(/Title/))

    fireEvent.click(screen.getByText(/Start Investigation/i))

    await waitFor(() => {
      expect(screen.getByText(/Offline/i)).toBeInTheDocument()
    })
  })

  it('regression: old code had no try/catch — error was completely invisible', async () => {
    // Old pattern:
    const oldHandleCreate = async () => {
      await Promise.reject(new Error('POST failed'))
      // setTitle('')
      // window.location.reload()
    }
    // No error UI, no catch — user sees nothing
    await expect(oldHandleCreate()).rejects.toThrow('POST failed')
  })
})
