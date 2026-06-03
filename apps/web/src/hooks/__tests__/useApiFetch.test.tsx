import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useApiFetch } from '../useApiFetch'

const originalFetch = globalThis.fetch

describe('useApiFetch', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('treats interval=0 as invalid (no polling)', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ value: 1 }),
    })

    const { result } = renderHook(() =>
      useApiFetch('/api/test', { interval: 0 })
    )

    await act(async () => {})
    expect(result.current.data).toEqual({ value: 1 })
    expect(result.current.loading).toBe(false)

    // Should NOT have polled again — interval=0 means no polling
    expect(globalThis.fetch).toHaveBeenCalledTimes(1)
  })

  it('aborts in-flight request on unmount', async () => {
    let capturedSignal: AbortSignal | null = null
    globalThis.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      capturedSignal = init?.signal || null
      return new Promise(() => {}) // never resolves
    })

    const { unmount } = renderHook(() => useApiFetch('/api/test'))

    await act(async () => {})
    expect(capturedSignal).not.toBeNull()
    expect(capturedSignal!.aborted).toBe(false)

    unmount()
    expect(capturedSignal!.aborted).toBe(true)
  })

  it('refetch blocks interval tick while in-flight', async () => {
    // Regression: when refetch() aborts a pending interval tick, the old
    // tick's .finally() used to clear a boolean inFlight flag, allowing the
    // next interval tick to overlap with the refetch that was still running.
    vi.useFakeTimers({ shouldAdvanceTime: true })
    let callCount = 0
    const pendingResolvers: Array<() => void> = []

    globalThis.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      callCount++
      return new Promise((resolve, reject) => {
        pendingResolvers.push(() =>
          resolve({ ok: true, json: async () => ({ value: callCount }) })
        )
        init?.signal?.addEventListener('abort', () => {
          const err = new Error('Aborted')
          ;(err as Error).name = 'AbortError'
          reject(err)
        })
      })
    })

    const { result } = renderHook(() =>
      useApiFetch('/api/test', { interval: 1000 })
    )

    // Initial fetch starts (call 1)
    await act(async () => {})
    expect(callCount).toBe(1)

    // Call refetch while initial is still pending — aborts call 1, starts call 2
    act(() => {
      result.current.refetch()
    })
    expect(callCount).toBe(2)

    // Advance past interval — refetch is still in-flight, tick must be blocked
    vi.advanceTimersByTime(1001)
    await act(async () => vi.advanceTimersByTimeAsync(0))
    expect(callCount).toBe(2)

    // Resolve the refetch fetch
    await act(async () => {
      pendingResolvers[1]()
    })

    // Advance past interval again — now tick should fire (call 3)
    vi.advanceTimersByTime(1001)
    await act(async () => vi.advanceTimersByTimeAsync(0))
    expect(callCount).toBe(3)

    vi.useRealTimers()
  })
})
