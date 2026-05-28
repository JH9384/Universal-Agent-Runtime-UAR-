import { useState, useEffect, useCallback, useRef } from 'react'
import { authHeaders } from '../utils/auth'

interface UseApiFetchOptions {
  /** Polling interval in ms; omit for single fetch. */
  interval?: number
}

interface UseApiFetchResult<T> {
  data: T | null
  loading: boolean
  error: string | null
}

/**
 * Fetch JSON from an API endpoint with automatic AbortController cleanup
 * and auth header injection.
 *
 * Usage:
 *   const { data, loading, error } = useApiFetch<HealthData>(
 *     '/api/health/dashboard',
 *     { interval: 30_000 }
 *   )
 */
export function useApiFetch<T>(
  url: string,
  options: UseApiFetchOptions = {}
): UseApiFetchResult<T> {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const abortRef = useRef<AbortController | null>(null)
  const hasFetchedRef = useRef(false)

  const fetchData = useCallback(async () => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl

    // Only show loading spinner on the initial fetch to avoid flicker
    // during subsequent polling refreshes.
    if (!hasFetchedRef.current) {
      setLoading(true)
    }
    setError(null)

    try {
      const res = await fetch(url, {
        headers: authHeaders(),
        signal: ctrl.signal,
      })
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`)
      }
      const json = (await res.json()) as T
      setData(json)
      hasFetchedRef.current = true
    } catch (e) {
      if ((e as Error)?.name === 'AbortError') return
      setError(String(e))
    } finally {
      setLoading(false)
    }
  }, [url])

  useEffect(() => {
    fetchData()
    if (!options.interval) return

    const id = setInterval(fetchData, options.interval)
    return () => {
      clearInterval(id)
      abortRef.current?.abort()
    }
  }, [fetchData, options.interval])

  return { data, loading, error }
}
