import { useEffect } from 'react'

/**
 * Preload lazy component chunks after initial render so they are
 * already in the cache when the user triggers a skill that needs them.
 *
 * Starts after a configurable delay to avoid competing with the main
 * bundle for bandwidth during first paint.
 *
 * Usage:
 *   usePreload([
 *     () => import('./GraphVisualizer'),
 *     () => import('./DataViz3D'),
 *   ])
 */
export function usePreload(
  importers: Array<() => Promise<unknown>>,
  delayMs = 3000
) {
  useEffect(() => {
    const timer = setTimeout(() => {
      // Fire off all imports in parallel; failures are silent
      importers.forEach((imp) => {
        imp().catch(() => {
          /* preload failure is non-fatal */
        })
      })
    }, delayMs)
    return () => clearTimeout(timer)
  }, [importers, delayMs])
}
