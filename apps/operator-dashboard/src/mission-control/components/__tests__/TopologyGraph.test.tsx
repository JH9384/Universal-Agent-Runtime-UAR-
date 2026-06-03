import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { TopologyGraph } from '../TopologyGraph'

// Mock the API client
vi.mock('../../../api/client', () => ({
  api: {
    circuitBreakers: vi.fn(),
    resetCircuitBreaker: vi.fn(),
  },
}))

import { api } from '../../../api/client'
import type { CircuitBreakerStates } from '../../../api/client'

describe('TopologyGraph', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('does not set state after unmount', async () => {
    const mockCircuitBreakers = vi.mocked(api.circuitBreakers)
    let resolvePromise: (value: CircuitBreakerStates) => void = () => {}

    mockCircuitBreakers.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvePromise = resolve
        })
    )

    const { unmount } = render(<TopologyGraph />)

    // Unmount before the API resolves
    unmount()

    // Now resolve the API call — if mounted guard is missing, React warns
    resolvePromise({
      status: 'ok',
      circuits: { test: { state: 'closed', failures: 0, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
    })

    expect(mockCircuitBreakers).toHaveBeenCalledTimes(1)
  })

  it('renders circuit breaker list after data loads', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      status: 'ok',
      circuits: {
        'skill-a': { state: 'closed', failures: 0, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 },
        'skill-b': { state: 'open', failures: 3, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 },
      },
    })

    render(<TopologyGraph />)

    await waitFor(() => {
      expect(screen.getByText('skill-a')).toBeInTheDocument()
      expect(screen.getByText('skill-b')).toBeInTheDocument()
    })
  })

  it('renders topology when backend returns 503 degraded', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      status: 'degraded',
      circuits: {
        'anthropic': { state: 'open', failures: 5, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 },
      },
    })

    render(<TopologyGraph />)

    await waitFor(() => {
      expect(screen.getByText('anthropic')).toBeInTheDocument()
      expect(screen.getByText('1 open')).toBeInTheDocument()
    })
  })

  it('double-click reset is guarded — only one API call issued', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      status: 'degraded',
      circuits: {
        'svc.a': { state: 'open', failures: 2, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 },
      },
    })
    let resolveReset: () => void = () => {}
    vi.mocked(api.resetCircuitBreaker).mockImplementation(
      () => new Promise((resolve) => { resolveReset = () => resolve({ status: 'reset' }) })
    )

    render(<TopologyGraph />)
    await waitFor(() => screen.getByText('svc.a'))

    const btn = screen.getByRole('button', { name: /Reset/i })
    fireEvent.click(btn)
    fireEvent.click(btn) // double-click

    expect(api.resetCircuitBreaker).toHaveBeenCalledTimes(1)
    resolveReset()
  })

  it('reset passes AbortSignal to API client', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      status: 'degraded',
      circuits: {
        'svc.a': { state: 'open', failures: 2, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 },
      },
    })
    vi.mocked(api.resetCircuitBreaker).mockResolvedValue({ status: 'reset' })

    render(<TopologyGraph />)
    await waitFor(() => screen.getByText('svc.a'))

    const btn = screen.getByRole('button', { name: /Reset/i })
    fireEvent.click(btn)

    await waitFor(() => {
      const calls = vi.mocked(api.resetCircuitBreaker).mock.calls
      expect(calls.length).toBeGreaterThan(0)
      const lastCall = calls[calls.length - 1]
      expect(lastCall[1]).toBeDefined()
      expect(lastCall[1]).toHaveProperty('signal')
    })
  })

  it('reset ignores AbortError and does not surface it as UI error', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      status: 'degraded',
      circuits: {
        'svc.a': { state: 'open', failures: 2, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 },
      },
    })
    const abortErr = new Error('Aborted')
    abortErr.name = 'AbortError'
    vi.mocked(api.resetCircuitBreaker).mockRejectedValue(abortErr)

    render(<TopologyGraph />)
    await waitFor(() => screen.getByText('svc.a'))

    const btn = screen.getByRole('button', { name: /Reset/i })
    fireEvent.click(btn)

    await waitFor(() => {
      expect(screen.queryByText(/AbortError/)).not.toBeInTheDocument()
    })
  })

  it('remount after unmount during in-flight does not leave loading stuck', async () => {
    const mockCircuitBreakers = vi.mocked(api.circuitBreakers)
    const resolvers: Array<(value: CircuitBreakerStates) => void> = []

    mockCircuitBreakers.mockImplementation(
      () =>
        new Promise((resolve) => {
          resolvers.push(resolve)
        })
    )

    const { unmount } = render(<TopologyGraph />)

    // Unmount while the first load is still in-flight
    unmount()

    // Re-mount — if inFlightRef was not reset, the new load() call would
    // bail at the guard and the component would stay stuck on "Loading..."
    render(<TopologyGraph />)

    // Resolve the SECOND api call (the re-mount's load)
    resolvers[1]({
      status: 'ok',
      circuits: { test: { state: 'closed', failures: 0, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
    })

    await waitFor(() => {
      expect(screen.getByText('test')).toBeInTheDocument()
    })

    // Two calls: first (abandoned), second (remount)
    expect(mockCircuitBreakers).toHaveBeenCalledTimes(2)
  })

  it('reset forces refresh even when a regular poll is in-flight', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const mockCircuitBreakers = vi.mocked(api.circuitBreakers)
    let callCount = 0
    const pendingResolvers: Array<(value: CircuitBreakerStates) => void> = []

    mockCircuitBreakers.mockImplementation(() => {
      callCount++
      if (callCount === 1) {
        return Promise.resolve({
          status: 'degraded',
          circuits: { 'svc.a': { state: 'open', failures: 2, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
        })
      }
      // Calls 2+ return a pending promise to simulate an in-flight request
      return new Promise((resolve) => {
        pendingResolvers.push(resolve)
      })
    })
    vi.mocked(api.resetCircuitBreaker).mockResolvedValue({ status: 'reset' })

    render(<TopologyGraph />)

    // Wait for initial load + UI
    await waitFor(() => screen.getByText('svc.a'))

    // Trigger a regular poll via timer (call #2, pending)
    vi.advanceTimersByTime(5000)
    await waitFor(() => expect(mockCircuitBreakers).toHaveBeenCalledTimes(2))

    // Click Reset while poll #2 is in-flight
    const btn = screen.getByRole('button', { name: /Reset/i })
    fireEvent.click(btn)

    // After reset API resolves, load(force=true) must bypass the inFlight
    // guard and issue a 3rd API call even though #2 is still pending.
    await waitFor(() => expect(mockCircuitBreakers).toHaveBeenCalledTimes(3))

    // Resolve the forced refresh so UI updates to closed state
    pendingResolvers[1]({
      status: 'ok',
      circuits: { 'svc.a': { state: 'closed', failures: 0, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
    })

    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Reset/i })).not.toBeInTheDocument()
    })

    vi.useRealTimers()
  })

  it('counter inFlightRef blocks overlapping interval tick after forced refresh resolves', async () => {
    // Regression: when force=true load finishes while a regular poll is still
    // in-flight, the old boolean inFlightRef would be cleared, allowing the
    // next interval tick to overlap with the still-pending regular poll.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    const mockCircuitBreakers = vi.mocked(api.circuitBreakers)
    const pendingResolvers: Array<(value: CircuitBreakerStates) => void> = []

    mockCircuitBreakers.mockImplementation(() =>
      new Promise((resolve) => {
        pendingResolvers.push(resolve)
      })
    )
    vi.mocked(api.resetCircuitBreaker).mockResolvedValue({ status: 'reset' })

    render(<TopologyGraph />)

    // Initial load (call 1) is pending — resolve it so UI renders
    pendingResolvers[0]({
      status: 'degraded',
      circuits: { 'svc.a': { state: 'open', failures: 2, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
    })
    await waitFor(() => screen.getByText('svc.a'))

    // Advance timer → interval tick (call 2, stays pending)
    vi.advanceTimersByTime(5000)
    await waitFor(() => expect(mockCircuitBreakers).toHaveBeenCalledTimes(2))

    // Click Reset → reset API resolves → forced load (call 3, stays pending)
    const btn = screen.getByRole('button', { name: /Reset/i })
    fireEvent.click(btn)
    await waitFor(() => expect(mockCircuitBreakers).toHaveBeenCalledTimes(3))

    // Resolve the forced refresh (call 3) first
    pendingResolvers[2]({
      status: 'ok',
      circuits: { 'svc.a': { state: 'closed', failures: 0, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
    })
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: /Reset/i })).not.toBeInTheDocument()
    })

    // Advance timer again while call 2 is STILL pending.
    // With the old boolean inFlightRef, this would have issued a 4th call.
    vi.advanceTimersByTime(5000)
    // Tick once to let any microtasks flush
    await vi.advanceTimersByTimeAsync(0)

    // Should still be exactly 3 calls — the regular poll (call 2) is in-flight,
    // so the interval tick must be blocked.
    expect(mockCircuitBreakers).toHaveBeenCalledTimes(3)

    // Cleanup: resolve the remaining pending regular poll so test exits clean
    pendingResolvers[1]({
      status: 'ok',
      circuits: { 'svc.a': { state: 'closed', failures: 0, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
    })

    vi.useRealTimers()
  })

  it('shows loading state during reset refresh', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      status: 'degraded',
      circuits: {
        'svc.a': { state: 'open', failures: 2, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 },
      },
    })
    vi.mocked(api.resetCircuitBreaker).mockResolvedValue({ status: 'reset' })

    render(<TopologyGraph />)
    await waitFor(() => screen.getByText('svc.a'))

    const btn = screen.getByRole('button', { name: /Reset/i })
    fireEvent.click(btn)

    // setLoading(true) should have fired immediately in handleReset
    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument()
    })
  })

  it('clears loading state when reset API fails', async () => {
    vi.mocked(api.circuitBreakers).mockResolvedValue({
      status: 'degraded',
      circuits: {
        'svc.a': { state: 'open', failures: 2, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 },
      },
    })
    vi.mocked(api.resetCircuitBreaker).mockRejectedValue(new Error('backend down'))

    render(<TopologyGraph />)
    await waitFor(() => screen.getByText('svc.a'))

    const btn = screen.getByRole('button', { name: /Reset/i })
    fireEvent.click(btn)

    // Loading appears immediately
    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument()
    })

    // After reset fails, loading must clear and error must appear
    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      expect(screen.getByText(/backend down/)).toBeInTheDocument()
    })
  })

  it('loading persists until post-reset load() completes', async () => {
    // Regression: .then() did not return load(), so .finally() ran
    // before load() finished, flashing stale data while fetch was in-flight.
    const pendingResolvers: Array<(value: CircuitBreakerStates) => void> = []
    vi.mocked(api.circuitBreakers).mockImplementation(() =>
      new Promise((resolve) => {
        pendingResolvers.push(resolve)
      })
    )
    vi.mocked(api.resetCircuitBreaker).mockResolvedValue({ status: 'reset' })

    render(<TopologyGraph />)

    // Resolve initial load so UI renders
    pendingResolvers[0]({
      status: 'degraded',
      circuits: { 'svc.a': { state: 'open', failures: 2, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
    })
    await waitFor(() => screen.getByText('svc.a'))

    const btn = screen.getByRole('button', { name: /Reset/i })
    fireEvent.click(btn)

    // Loading appears immediately
    await waitFor(() => {
      expect(screen.getByText('Loading...')).toBeInTheDocument()
    })

    // Reset API resolves, then load() starts (call 2, still pending).
    // With the old code, .finally() would have already cleared loading.
    // With the fix, loading must still be true.
    await waitFor(() => expect(vi.mocked(api.circuitBreakers)).toHaveBeenCalledTimes(2))
    expect(screen.getByText('Loading...')).toBeInTheDocument()

    // Now resolve the post-reset load()
    pendingResolvers[1]({
      status: 'ok',
      circuits: { 'svc.a': { state: 'closed', failures: 0, half_open_count: 0, half_open_successes: 0, last_failure_time: 0 } },
    })

    // Only now should loading clear
    await waitFor(() => {
      expect(screen.queryByText('Loading...')).not.toBeInTheDocument()
      expect(screen.queryByRole('button', { name: /Reset/i })).not.toBeInTheDocument()
    })
  })
})
