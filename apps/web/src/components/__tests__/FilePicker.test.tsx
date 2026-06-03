import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { FilePicker } from '../FilePicker'

const originalFetch = globalThis.fetch

function fakeBrowseResponse(path: string) {
  return {
    ok: true,
    json: async () => ({
      path,
      parent: path === '/project' ? null : '/project',
      is_dir: true,
      recursive: false,
      file_count: 0,
      dir_count: 0,
      total_bytes: 0,
      truncated: false,
      by_extension: {},
      entries: [],
    }),
  }
}

describe('FilePicker', () => {
  beforeEach(() => {
    globalThis.fetch = vi.fn()
  })

  afterEach(() => {
    globalThis.fetch = originalFetch
    vi.restoreAllMocks()
  })

  it('busy stays true when overlapping load() calls abort the old one', async () => {
    // Regression: clicking a breadcrumb while a previous load is still
    // pending would abort the old fetch; its .finally() then cleared
    // busy while the new load was still in-flight.
    const pendingResolvers: Array<() => void> = []
    let callCount = 0

    globalThis.fetch = vi.fn().mockImplementation((_url: string, init?: RequestInit) => {
      callCount++
      return new Promise((resolve, reject) => {
        pendingResolvers.push(() =>
          resolve(fakeBrowseResponse('/project'))
        )
        init?.signal?.addEventListener('abort', () => {
          const err = new Error('Aborted')
          ;(err as Error).name = 'AbortError'
          reject(err)
        })
      })
    })

    render(
      <FilePicker
        open
        initialPath="/project"
        projectRoot="/project"
        presets={[]}
        onClose={() => {}}
        onPick={() => {}}
      />
    )

    // Initial load starts (call 1) — wait for it to render
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(1))

    // Resolve initial load so UI is interactive
    pendingResolvers[0]()
    await waitFor(() => {
      expect(screen.queryByText('Loading…')).not.toBeInTheDocument()
    })

    // Click the root breadcrumb to trigger a second load
    const rootBtn = screen.getByText('project_root')
    fireEvent.click(rootBtn)

    // New load starts (call 2), old one is aborted
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalledTimes(2))

    // Busy should still be true because call 2 is in-flight
    expect(screen.getByText('Loading…')).toBeInTheDocument()

    // Resolve the second load
    pendingResolvers[1]()
    await waitFor(() => {
      expect(screen.queryByText('Loading…')).not.toBeInTheDocument()
    })
  })
})
