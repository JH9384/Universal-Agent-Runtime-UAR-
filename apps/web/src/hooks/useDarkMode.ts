import { useEffect, useState } from 'react'

const STORAGE_KEY = 'uar.darkMode'

function readSavedDarkMode(): boolean | null {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved !== null) return saved === 'true'
  } catch {
    /* localStorage unavailable */
  }
  return null
}

function readSystemDarkMode(): boolean {
  if (typeof window !== 'undefined' && window.matchMedia) {
    return window.matchMedia('(prefers-color-scheme: dark)').matches
  }
  return false
}

function readInitialDarkMode(): boolean {
  return readSavedDarkMode() ?? readSystemDarkMode()
}

/**
 * Persist a dark-mode preference and toggle the `dark` class on
 * `<html>`. Falls back to the system color-scheme preference when
 * localStorage is unavailable (e.g. private browsing). Reacts to
 * system theme changes when no explicit preference has been saved.
 *
 * Usage:
 *   const [darkMode, setDarkMode] = useDarkMode()
 */
export function useDarkMode(): [boolean, (next: boolean) => void] {
  const [darkMode, setDarkMode] = useState<boolean>(readInitialDarkMode)

  useEffect(() => {
    if (typeof document === 'undefined') return
    const root = document.documentElement
    if (darkMode) root.classList.add('dark')
    else root.classList.remove('dark')
    try {
      localStorage.setItem(STORAGE_KEY, String(darkMode))
    } catch {
      /* localStorage unavailable; preference will reset on reload */
    }
  }, [darkMode])

  // Listen for system preference changes when no explicit preference is saved
  useEffect(() => {
    if (typeof window === 'undefined' || !window.matchMedia) return
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => {
      // Only react if user hasn't explicitly set a preference
      if (readSavedDarkMode() === null) {
        setDarkMode(e.matches)
      }
    }
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [])

  return [darkMode, setDarkMode]
}
