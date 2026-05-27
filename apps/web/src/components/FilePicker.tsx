import { useCallback, useEffect, useRef, useState } from 'react'
import { authHeaders } from '../utils/auth'
import styles from './UARPanel.module.css'

export type Preset = { name: string; path: string }
export type BrowseEntry = {
  name: string
  path: string
  size: number
  ext: string
  is_dir: boolean
}
export type BrowseResult = {
  path: string
  parent: string | null
  is_dir: boolean
  recursive: boolean
  file_count: number
  dir_count: number
  total_bytes: number
  truncated: boolean
  by_extension: Record<string, number>
  entries: BrowseEntry[]
}

function human(bytes: number) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(2)} MB`
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`
}

interface FilePickerProps {
  open: boolean
  initialPath: string
  projectRoot: string
  presets: Preset[]
  onClose: () => void
  onPick: (path: string) => void
}

/**
 * Modal file/folder picker scoped to PROJECT_ROOT.
 *
 * Backed by `GET /api/uar/docs/browse`. Supports breadcrumbs, recursive
 * listing, and a free-text path field. Extracted from UARPanel.tsx to
 * keep that file's surface manageable.
 */
export function FilePicker(props: FilePickerProps) {
  const { open, initialPath, projectRoot, presets, onClose, onPick } = props
  const [path, setPath] = useState(initialPath ?? projectRoot)
  const [data, setData] = useState<BrowseResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [filter, setFilter] = useState('')
  const abortRef = useRef<AbortController | null>(null)

  const load = useCallback(async (p: string, recursive = false) => {
    abortRef.current?.abort()
    const ctrl = new AbortController()
    abortRef.current = ctrl
    setBusy(true)
    setErr(null)
    try {
      const r = await fetch(
        `/api/uar/docs/browse?path=${encodeURIComponent(p)}&limit=500&recursive=${recursive}`,
        { signal: ctrl.signal, headers: authHeaders() },
      )
      const j = await r.json()
      if (ctrl.signal.aborted) return
      if (!r.ok) setErr(j.message || j.error || `HTTP ${r.status}`)
      else {
        setData(j)
        setPath(j.path || p)
      }
    } catch (e: unknown) {
      if (e instanceof Error && e.name === 'AbortError') return
      setErr(e instanceof Error ? e.message : 'Browse failed')
    } finally {
      if (abortRef.current === ctrl) {
        abortRef.current = null
      }
      setBusy(false)
    }
  }, [])

  useEffect(() => {
    if (open) load(initialPath || projectRoot)
    return () => { abortRef.current?.abort() }
  }, [open, initialPath, projectRoot, load])

  if (!open) return null

  // Breadcrumbs
  const breadcrumbs: { label: string; path: string }[] = []
  if (data) {
    let acc = projectRoot
    breadcrumbs.push({ label: 'project_root', path: projectRoot })
    const rel = data.path.startsWith(projectRoot)
      ? data.path.slice(projectRoot.length).replace(/^\/+/, '')
      : data.path
    if (rel) {
      for (const part of rel.split('/').filter(Boolean)) {
        acc = `${acc}/${part}`
        breadcrumbs.push({ label: part, path: acc })
      }
    }
  }

  const filtered = (data?.entries || []).filter(
    (e) => !filter || (e.name || '').toLowerCase().includes(filter.toLowerCase()),
  )

  return (
    <div
      onClick={onClose}
      className={styles.modalOverlay}
      role="presentation"
    >
      <div
        onClick={(e: React.MouseEvent) => e.stopPropagation()}
        className={styles.modalContent}
        role="dialog"
        aria-modal="true"
        aria-label="Pick a folder or file"
      >
        {/* Header */}
        <div className={styles.modalHeader}>
          <strong>Pick a folder or file</strong>
          <span className={styles.modalHeaderInfo}>
            (must be within PROJECT_ROOT)
          </span>
          <button
            onClick={onClose}
            className={styles.modalCloseButton}
            aria-label="Close picker"
          >
            ✕
          </button>
        </div>

        {/* Presets row */}
        <div className={styles.presetsRow}>
          <span className={styles.quickLabel}>Quick:</span>
          <button
            onClick={() => load(projectRoot)}
            className={styles.presetButton}
          >
            / root
          </button>
          {presets.map((p) => (
            <button
              key={p.path}
              onClick={() => load(p.path)}
              className={styles.presetButton}
            >
              {p.name}
            </button>
          ))}
        </div>

        {/* Breadcrumbs + nav */}
        <div className={styles.navRow}>
          <button
            onClick={() => data?.parent && load(data.parent)}
            disabled={!data?.parent || busy}
            title="Parent"
            aria-label="Go to parent folder"
            className={styles.navButton}
          >
            ⬆
          </button>
          <button
            onClick={() => data && load(data.path, true)}
            disabled={busy || !data?.is_dir}
            className={styles.navButton}
            title="Recursive listing"
            aria-label="Recursive listing"
          >
            ⤓
          </button>
          <button
            onClick={() => data && load(data.path)}
            disabled={busy}
            className={styles.navButton}
            title="Reload"
            aria-label="Reload"
          >
            ⟳
          </button>
          <span className={styles.breadcrumbContainer}>
            {breadcrumbs.map((b, i) => (
              <span key={b.path}>
                <button
                  onClick={() => load(b.path)}
                  className={styles.breadcrumbLink}
                  aria-label={`Navigate to ${b.label}`}
                >
                  {b.label}
                </button>
                {i < breadcrumbs.length - 1 && (
                  <span className={styles.breadcrumbSeparator}> / </span>
                )}
              </span>
            ))}
          </span>
        </div>

        {/* Filter + manual path */}
        <div className={styles.filterRow}>
          <input
            placeholder="Filter (filename contains…)"
            value={filter}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setFilter(e.target.value)
            }
            className={styles.filterInput}
            aria-label="Filter entries by name"
          />
          <input
            placeholder="Or type a path and press Enter"
            value={path}
            onChange={(e: React.ChangeEvent<HTMLInputElement>) =>
              setPath(e.target.value)
            }
            onKeyDown={(e: React.KeyboardEvent<HTMLInputElement>) => {
              if (e.key === 'Enter') load(path)
            }}
            className={styles.pathInput}
            aria-label="Path"
          />
        </div>

        {/* Body */}
        <div className={styles.modalBody}>
          {err && <div className={styles.errorText}>Error: {err}</div>}
          {busy && <div className={styles.loadingText}>Loading…</div>}
          {!busy && !err && data && (
            <>
              <div className={styles.statsBar}>
                <strong>{data.dir_count}</strong> dirs ·{' '}
                <strong>{data.file_count}</strong> files
                {data.total_bytes > 0 && (
                  <>
                    {' '}
                    · <strong>{human(data.total_bytes)}</strong>
                  </>
                )}
                {data.truncated && (
                  <span className={styles.truncatedText}> · truncated</span>
                )}
                {data.recursive && (
                  <span className={styles.recursiveText}> · recursive</span>
                )}
                {Object.keys(data.by_extension).length > 0 && (
                  <span className={styles.extensionInfo}>
                    {Object.entries(data.by_extension)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 8)
                      .map(([k, v]) => `${k}:${v}`)
                      .join('  ')}
                  </span>
                )}
              </div>
              <div className={styles.fileList}>
                {filtered.map((e) => (
                  <div
                    key={e.path}
                    onClick={() =>
                      e.is_dir ? load(e.path) : onPick(e.path)
                    }
                    onDoubleClick={() => onPick(e.path)}
                    className={`${styles.fileItem} ${
                      e.is_dir ? styles.fileItemDir : ''
                    }`}
                    title={
                      e.is_dir ? 'Click to open' : 'Click to select this file'
                    }
                    role="button"
                    tabIndex={0}
                    aria-label={`${e.is_dir ? 'Folder' : 'File'}: ${e.name}`}
                    onKeyDown={(ev) => {
                      if (ev.key === 'Enter' || ev.key === ' ') {
                        ev.preventDefault()
                        if (e.is_dir) load(e.path)
                        else onPick(e.path)
                      }
                    }}
                  >
                    <span>
                      {e.is_dir ? '📁 ' : '📄 '}
                      <span
                        className={
                          e.is_dir ? styles.fileIconDir : styles.fileIcon
                        }
                      >
                        {e.name}
                      </span>
                      {e.is_dir && '/'}
                    </span>
                    <span className={styles.fileSize}>
                      {e.is_dir ? '' : human(e.size)}
                    </span>
                  </div>
                ))}
                {filtered.length === 0 && (
                  <div className={styles.noEntries}>(no entries)</div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className={styles.modalFooter}>
          <span className={styles.selectedPath}>
            Selected: {data?.path || '(none)'}
          </span>
          <button onClick={onClose} className={styles.footerButton}>
            Cancel
          </button>
          <button
            onClick={() => data && onPick(data.path)}
            disabled={!data}
            className={styles.primaryButton}
          >
            Use this folder
          </button>
        </div>
      </div>
    </div>
  )
}
