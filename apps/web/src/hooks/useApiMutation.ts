import { useState, useCallback } from 'react'
import { authHeaders } from '../utils/auth'

interface UseApiMutationOptions<T> {
  onSuccess?: () => void
  onError?: (msg: string) => void
}

interface UseApiMutationResult<T> {
  mutate: (body: unknown) => Promise<void>
  loading: boolean
  error: string | null
  data: T | null
  reset: () => void
}

/**
 * Perform a JSON POST/PUT/PATCH mutation with auth header injection,
 * loading state, and structured error parsing.
 *
 * Usage:
 *   const { mutate, loading, error } = useApiMutation<CredentialOut>(
 *     '/api/uar/credentials'
 *   )
 *   await mutate({ cred_id: 'foo', name: 'bar', value: 'baz' })
 */
export function useApiMutation<T>(
  url: string,
  options: UseApiMutationOptions<T> = {}
): UseApiMutationResult<T> {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [data, setData] = useState<T | null>(null)

  const reset = useCallback(() => {
    setLoading(false)
    setError(null)
    setData(null)
  }, [])

  const mutate = useCallback(
    async (body: unknown) => {
      setLoading(true)
      setError(null)
      try {
        const res = await fetch(url, {
          method: 'POST',
          headers: authHeaders({ 'Content-Type': 'application/json' }),
          body: JSON.stringify(body),
        })
        if (!res.ok) {
          const text = await res.text()
          let msg = `HTTP ${res.status}`
          try {
            const json = JSON.parse(text)
            if (json.detail?.message) {
              msg = json.detail.message
            } else if (json.detail?.error) {
              msg = `${json.detail.error}: ${json.detail.message || ''}`
            } else if (json.message) {
              msg = json.message
            }
          } catch {
            // non-JSON error body — keep default
          }
          throw new Error(msg)
        }
        const json = (await res.json()) as T
        setData(json)
        options.onSuccess?.()
      } catch (e) {
        const msg = String(e)
        setError(msg)
        options.onError?.(msg)
        throw e
      } finally {
        setLoading(false)
      }
    },
    [url]
  )

  return { mutate, loading, error, data, reset }
}
