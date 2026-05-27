/** Safely access localStorage (may be unavailable in tests / privacy mode). */
export function getLocalStorage(): Storage | null {
  try {
    const storage = globalThis.localStorage
    if (
      storage &&
      typeof storage.getItem === 'function' &&
      typeof storage.setItem === 'function' &&
      typeof storage.removeItem === 'function'
    ) {
      return storage
    }
  } catch {
    /* localStorage can be unavailable in tests, SSR, or privacy modes */
  }
  return null
}

/** Build Authorization header when API key is present in localStorage. */
export function authHeaders(init?: Record<string, string>): Record<string, string> {
  const key = getLocalStorage()?.getItem('uar_api_key')
  if (!key) return init || {}
  return { Authorization: `Bearer ${key}`, ...init }
}
