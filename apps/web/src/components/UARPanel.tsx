import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'
import { SkillGuide } from './SkillGuide'
import styles from './UARPanel.module.css'

const MAX_EVENTS = 1000
const RECENT_KEY = 'uar.recentPaths'
const RECENT_MAX = 8

const AVAILABLE_SKILLS = [
  { id: 'doc_ingest',     label: 'doc_ingest',     desc: 'Read files from input_path (.md .txt .py .ts .json …)' },
  { id: 'dependency_map', label: 'dependency_map', desc: 'Build a dependency graph between artifacts' },
  { id: 'section_sum',    label: 'section_sum',    desc: 'Summarize document sections' },
  { id: 'sum_review',     label: 'sum_review',     desc: 'Final review of pipeline outputs' },
  { id: 'ollama_generate', label: 'ollama_generate', desc: 'Send goal + ingested docs to local Ollama model (requires Ollama running)' },
  { id: 'graphrag_init',   label: 'graphrag_init',   desc: 'Initialize GraphRAG workspace (one-time setup)' },
  { id: 'graphrag_index',  label: 'graphrag_index',  desc: 'Build a GraphRAG knowledge graph over input_path (slow; one-time)' },
  { id: 'graphrag_query',  label: 'graphrag_query',  desc: 'Query the GraphRAG index. Metadata: graphrag_method=local|global' },
  { id: 'autonomi_upload',   label: 'autonomi_upload',   desc: 'Upload file/dir to Autonomi decentralized storage (requires autonomi package + wallet)' },
  { id: 'autonomi_download', label: 'autonomi_download', desc: 'Download a file from Autonomi by address (requires autonomi package)' },
  { id: 'autonomi_status',   label: 'autonomi_status',   desc: 'Check Autonomi client and wallet status' },
  { id: 'alm_analyze',      label: 'alm_analyze',      desc: 'Analyze formal grammar specifications (BNF, EBNF) with ALM (requires ALM service)' },
  { id: 'alm_generate',     label: 'alm_generate',     desc: 'Generate token sequences from a prefix using ALM (requires ALM service)' },
  { id: 'alm_verify',       label: 'alm_verify',       desc: 'Validate text against ALM grammar (requires ALM service)' },
  { id: 'math_compute',    label: 'math_compute',    desc: 'Symbolic math with SymPy: solve, differentiate, integrate, simplify (requires sympy)' },
  { id: 'cipher_ops',      label: 'cipher_ops',      desc: 'Cryptographic operations: encrypt, decrypt, hash, sign (requires pycryptodome)' },
  { id: 'physics_compute', label: 'physics_compute', desc: 'Physics & astronomy: unit conversion, coordinate transforms, cosmology (requires astropy)' },
]

const GOAL_TEMPLATES = [
  'Summarize the project',
  'Document the architecture',
  'Build a dependency map of the codebase',
  'Review and identify inconsistencies in docs',
  'Index all source files for retrieval',
]

type Recipe = { id: string; label: string; skills: string[]; hint: string }
type UARError = { code?: string; message: string; requestId?: string; timestamp: number }
const RECIPES: Recipe[] = [
  { id: 'review',    label: '🦙 Ollama review',   skills: ['doc_ingest', 'ollama_generate'], hint: 'Quick LLM review of library docs' },
  { id: 'deps',      label: '🕸️ Dep map',          skills: ['doc_ingest', 'dependency_map', 'sum_review'], hint: 'Build a dependency graph' },
  { id: 'gr_index',  label: '📚 GraphRAG index',  skills: ['graphrag_index'], hint: 'Build the knowledge graph (slow, one-time)' },
  { id: 'gr_query',  label: '🔎 GraphRAG query',  skills: ['graphrag_query'], hint: 'Query an existing graph' },
  { id: 'gr_full',   label: '⚡ Full pipeline',    skills: ['graphrag_index', 'graphrag_query'], hint: 'Index then query (very slow)' },
  { id: 'auto_up',   label: '☁️ Autonomi upload',  skills: ['autonomi_upload'], hint: 'Upload current input_path to Autonomi' },
  { id: 'auto_down', label: '☁️ Autonomi download', skills: ['autonomi_download'], hint: 'Download from Autonomi address' },
  { id: 'auto_status', label: '☁️ Autonomi status',  skills: ['autonomi_status'], hint: 'Check Autonomi connectivity' },
]

type Preset = { name: string; path: string }
type BrowseEntry = { name: string; path: string; size: number; ext: string; is_dir: boolean }
type LibFile = { name: string; path: string; size: number; ext: string; mtime: number }
type BrowseResult = {
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
  return `${(bytes / 1024 / 1024).toFixed(2)} MB`
}

// ============================================================
// FilePicker modal
// ============================================================
function FilePicker(props: {
  open: boolean
  initialPath: string
  projectRoot: string
  presets: Preset[]
  onClose: () => void
  onPick: (path: string) => void
}) {
  const { open, initialPath, projectRoot, presets, onClose, onPick } = props
  const [path, setPath] = useState(initialPath || projectRoot)
  const [data, setData] = useState<BrowseResult | null>(null)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const [filter, setFilter] = useState('')

  const load = useCallback(async (p: string, recursive = false) => {
    setBusy(true); setErr(null)
    try {
      const r = await fetch(
        `/api/uar/docs/browse?path=${encodeURIComponent(p)}&limit=500&recursive=${recursive}`,
      )
      const j = await r.json()
      if (!r.ok) setErr(j.message || j.error || `HTTP ${r.status}`)
      else { setData(j); setPath(j.path || p) }
    } catch (e: any) {
      setErr(e?.message || 'Browse failed')
    } finally { setBusy(false) }
  }, [])

  useEffect(() => {
    if (open) load(initialPath || projectRoot)
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
    (e) => !filter || e.name.toLowerCase().includes(filter.toLowerCase()),
  )

  return (
    <div onClick={onClose} className={styles.modalOverlay}>
      <div onClick={(e: any) => e.stopPropagation()} className={styles.modalContent}>
        {/* Header */}
        <div className={styles.modalHeader}>
          <strong>Pick a folder or file</strong>
          <span className={styles.modalHeaderInfo}>(must be within PROJECT_ROOT)</span>
          <button onClick={onClose} className={styles.modalCloseButton}>✕</button>
        </div>

        {/* Presets row */}
        <div className={styles.presetsRow}>
          <span className={styles.quickLabel}>Quick:</span>
          <button onClick={() => load(projectRoot)} className={styles.presetButton}>/ root</button>
          {presets.map((p) => (
            <button key={p.path} onClick={() => load(p.path)} className={styles.presetButton}>
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
            className={styles.navButton}
          >⬆</button>
          <button onClick={() => data && load(data.path, true)} disabled={busy || !data?.is_dir} className={styles.navButton} title="Recursive listing">⤓</button>
          <button onClick={() => data && load(data.path)} disabled={busy} className={styles.navButton} title="Reload">⟳</button>
          <span className={styles.breadcrumbContainer}>
            {breadcrumbs.map((b, i) => (
              <span key={b.path}>
                <a onClick={() => load(b.path)} className={styles.breadcrumbLink}>{b.label}</a>
                {i < breadcrumbs.length - 1 && <span className={styles.breadcrumbSeparator}> / </span>}
              </span>
            ))}
          </span>
        </div>

        {/* Filter + manual path */}
        <div className={styles.filterRow}>
          <input
            placeholder="Filter (filename contains…)"
            value={filter}
            onChange={(e: any) => setFilter(e.target.value)}
            className={styles.filterInput}
          />
          <input
            placeholder="Or type a path and press Enter"
            value={path}
            onChange={(e: any) => setPath(e.target.value)}
            onKeyDown={(e: any) => { if (e.key === 'Enter') load(path) }}
            className={styles.pathInput}
          />
        </div>

        {/* Body */}
        <div className={styles.modalBody}>
          {err && <div className={styles.errorText}>Error: {err}</div>}
          {busy && <div className={styles.loadingText}>Loading…</div>}
          {!busy && !err && data && (
            <>
              <div className={styles.statsBar}>
                <strong>{data.dir_count}</strong> dirs · <strong>{data.file_count}</strong> files
                {data.total_bytes > 0 && <> · <strong>{human(data.total_bytes)}</strong></>}
                {data.truncated && <span className={styles.truncatedText}> · truncated</span>}
                {data.recursive && <span className={styles.recursiveText}> · recursive</span>}
                {Object.keys(data.by_extension).length > 0 && (
                  <span className={styles.extensionInfo}>
                    {Object.entries(data.by_extension).sort((a, b) => b[1] - a[1])
                      .slice(0, 8).map(([k, v]) => `${k}:${v}`).join('  ')}
                  </span>
                )}
              </div>
              <div className={styles.fileList}>
                {filtered.map((e) => (
                  <div
                    key={e.path}
                    onClick={() => e.is_dir ? load(e.path) : onPick(e.path)}
                    onDoubleClick={() => onPick(e.path)}
                    className={`${styles.fileItem} ${e.is_dir ? styles.fileItemDir : ''}`}
                    title={e.is_dir ? 'Click to open' : 'Click to select this file'}
                  >
                    <span>
                      {e.is_dir ? '📁 ' : '📄 '}
                      <span className={`${e.is_dir ? styles.fileIconDir : styles.fileIcon}`}>{e.name}</span>
                      {e.is_dir && '/'}
                    </span>
                    <span className={styles.fileSize}>{e.is_dir ? '' : human(e.size)}</span>
                  </div>
                ))}
                {filtered.length === 0 && <div className={styles.noEntries}>(no entries)</div>}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div className={styles.modalFooter}>
          <span className={styles.selectedPath}>
            Selected: {data?.path || '(none)'}
          </span>
          <button onClick={onClose} className={styles.footerButton}>Cancel</button>
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

// ============================================================
// Main panel
// ============================================================
export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [inputPath, setInputPath] = useState('')
  const [selectedSkills, setSelectedSkills] = useState<string[]>(['doc_ingest', 'dependency_map', 'sum_review'])
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<UARError | null>(null)
  const [pickerOpen, setPickerOpen] = useState(false)
  const [skillGuideOpen, setSkillGuideOpen] = useState(false)
  const [currentSkill, setCurrentSkill] = useState<string>('')
  const [startTime, setStartTime] = useState<number>(0)
  // Advanced overrides
  const [graphragMethod, setGraphragMethod] = useState<'local' | 'global'>('local')
  const [ollamaModel, setOllamaModel] = useState<string>('')
  // Autonomi overrides
  const [autonomiKey, setAutonomiKey] = useState<string>('')
  const [autonomiNetwork, setAutonomiNetwork] = useState<'testnet' | 'mainnet'>('testnet')
  const [autonomiPublic, setAutonomiPublic] = useState<boolean>(false)
  const [autonomiAddress, setAutonomiAddress] = useState<string>('')

  // Document management
  const [presets, setPresets] = useState<Preset[]>([])
  const [projectRoot, setProjectRoot] = useState<string>('')
  const [libraryPath, setLibraryPath] = useState<string>('')
  const [library, setLibrary] = useState<LibFile[]>([])
  const [libBusy, setLibBusy] = useState(false)
  const [dragActive, setDragActive] = useState(false)
  const [uploadMsg, setUploadMsg] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [recent, setRecent] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
  })

  const abortControllerRef = useRef<AbortController | null>(null)
  const eventCountRef = useRef(0)

  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsRunning(false)
    setCurrentSkill('')
    setStartTime(0)
  }, [])

  useEffect(() => cleanup, [cleanup])

  const refreshLibrary = useCallback(async () => {
    setLibBusy(true)
    try {
      const r = await fetch('/api/uar/docs/library')
      const j = await r.json()
      if (r.ok) {
        setLibrary(j.entries || [])
        setLibraryPath(j.library || '')
      }
    } catch { /* ignore */ }
    finally { setLibBusy(false) }
  }, [])

  useEffect(() => {
    fetch('/api/uar/docs/presets')
      .then((r) => r.json())
      .then((d) => {
        setPresets(d.presets || [])
        setProjectRoot(d.project_root || '')
        if (d.library) {
          setLibraryPath(d.library)
          // Default input_path to the library on first load
          setInputPath((cur) => cur || d.library)
        }
      })
      .catch(() => {})
    refreshLibrary()
  }, [refreshLibrary])

  const uploadFiles = useCallback(async (fileList: FileList | File[]) => {
    const files = Array.from(fileList)
    if (files.length === 0) return
    setUploadMsg(`Uploading ${files.length} file(s)…`)
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f, f.name))
    const ctrl = new AbortController()
    const timer = setTimeout(() => ctrl.abort(), 60_000) // 60s safety
    try {
      const r = await fetch('/api/uar/docs/upload', {
        method: 'POST', body: fd, signal: ctrl.signal,
      })
      clearTimeout(timer)
      const j = await r.json()
      if (!r.ok) {
        setUploadMsg(`Upload failed: ${j.message || j.error || r.status}`)
      } else {
        const okN = (j.saved || []).length
        const badN = (j.rejected || []).length
        const rejNotes = (j.rejected || []).map((x: any) => `${x.name} (${x.reason})`).join(', ')
        setUploadMsg(`Saved ${okN}${badN ? ` · rejected ${badN}: ${rejNotes}` : ''}`)
        await refreshLibrary()
        // If exactly one file uploaded, pre-select it
        if (okN === 1) setInputPath(j.saved[0].path)
        else if (okN > 0 && j.library) setInputPath(j.library)
      }
    } catch (e: any) {
      setUploadMsg(`Upload error: ${e?.message || 'unknown'}`)
    }
  }, [refreshLibrary])

  const deleteLibFile = async (name: string) => {
    if (!confirm(`Delete "${name}" from library?`)) return
    try {
      const r = await fetch(`/api/uar/docs/library?name=${encodeURIComponent(name)}`, { method: 'DELETE' })
      if (r.ok) refreshLibrary()
      else {
        const j = await r.json().catch(() => ({}))
        setUploadMsg(`Delete failed: ${j.message || r.status}`)
      }
    } catch (e: any) {
      setUploadMsg(`Delete error: ${e?.message}`)
    }
  }

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setDragActive(false)
    if (e.dataTransfer?.files?.length) uploadFiles(e.dataTransfer.files)
  }, [uploadFiles])

  const onDragOver = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setDragActive(true) }
  const onDragLeave = (e: React.DragEvent) => { e.preventDefault(); e.stopPropagation(); setDragActive(false) }

  // ESC closes picker
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setPickerOpen(false) }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const pushRecent = (p: string) => {
    if (!p.trim()) return
    setRecent((prev) => {
      const next = [p, ...prev.filter((x) => x !== p)].slice(0, RECENT_MAX)
      try { localStorage.setItem(RECENT_KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }

  const clearRecent = () => {
    setRecent([])
    try { localStorage.removeItem(RECENT_KEY) } catch {}
  }

  const toggleSkill = (id: string) => {
    setSelectedSkills((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    )
  }

  const onPick = (p: string) => {
    setInputPath(p)
    pushRecent(p)
    setPickerOpen(false)
  }

  const copyPath = async () => {
    try {
      await navigator.clipboard.writeText(inputPath)
    } catch {}
  }

  const runStream = useCallback(async () => {
    setEvents([]); setGraph(null); setError(null)
    setIsRunning(true)
    eventCountRef.current = 0
    abortControllerRef.current = new AbortController()

    const body: any = { goal, skills: selectedSkills }
    if (inputPath.trim()) { body.input_path = inputPath.trim(); pushRecent(inputPath.trim()) }
    const meta: any = {}
    if (selectedSkills.includes('graphrag_query')) {
      meta.graphrag_method = graphragMethod
      meta.graphrag_query = goal
    }
    if (ollamaModel.trim() && selectedSkills.includes('ollama_generate')) {
      meta.ollama_model = ollamaModel.trim()
    }
    if (selectedSkills.includes('autonomi_upload') || selectedSkills.includes('autonomi_download') || selectedSkills.includes('autonomi_status')) {
      if (autonomiKey.trim()) meta.autonomi_private_key = autonomiKey.trim()
      meta.autonomi_network = autonomiNetwork
      if (selectedSkills.includes('autonomi_upload')) {
        meta.autonomi_public = autonomiPublic
      }
      if (selectedSkills.includes('autonomi_download') && autonomiAddress.trim()) {
        meta.autonomi_address = autonomiAddress.trim()
      }
    }
    if (Object.keys(meta).length) body.metadata = meta

    try {
      setCurrentSkill(selectedSkills[0] || 'Starting')
      setStartTime(Date.now())
      const res = await fetch('/api/uar/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
        signal: abortControllerRef.current.signal,
      })
      if (!res.ok) {
        const text = await res.text().catch(() => '')
        throw new Error(`HTTP ${res.status}: ${res.statusText}${text ? ` — ${text}` : ''}`)
      }
      const reader = res.body?.getReader()
      const decoder = new TextDecoder()
      if (!reader) throw new Error('No response body reader available')

      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        if (abortControllerRef.current?.signal.aborted) break
        buffer += decoder.decode(value, { stream: true })
        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''
        for (const part of parts) {
          for (const line of part.split('\n')) {
            if (!line.startsWith('data:')) continue
            try {
              const json = JSON.parse(line.replace('data: ', ''))
              eventCountRef.current++
              if (eventCountRef.current > MAX_EVENTS) {
                abortControllerRef.current?.abort()
                setError({ message: `Event limit reached (${MAX_EVENTS}).`, timestamp: Date.now() })
                setIsRunning(false)
                return
              }
              setEvents((prev) => {
                const next = prev.length >= MAX_EVENTS ? prev.slice(1) : prev
                return [...next, json]
              })
              if (json.type === 'skill_start' && json.skill) setCurrentSkill(json.skill)
              if (json.type === 'skill_complete' && json.skill) setCurrentSkill(`Completed: ${json.skill}`)
              if (json.type === 'orchestration_plan' && json.payload?.graph) setGraph(json.payload.graph)
              if (json.run?.final_context?.dependency_map) setGraph(json.run.final_context.dependency_map)
              if (json.type === 'error' && json.error) setError({ message: json.error, timestamp: Date.now() })
            } catch (parseError) {
              console.error('Failed to parse SSE data:', parseError, 'Data:', line)
              setError({ message: 'Failed to parse server response', timestamp: Date.now() })
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') return
      setError({ message: err instanceof Error ? err.message : 'Unknown error occurred', timestamp: Date.now() })
    } finally {
      setIsRunning(false)
      abortControllerRef.current = null
    }
  }, [goal, inputPath, selectedSkills])

  const stopStream = useCallback(() => cleanup(), [cleanup])

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] }
    const nodeIndex = new Map<string, string>()
    const nodes = (graph.nodes || []).map((n: any, i: number) => {
      const nodeId = n.id || n.skill || String(i)
      nodeIndex.set(nodeId, String(i))
      return {
        id: String(i),
        data: { label: n.skill || String(nodeId).split('/').pop(), type: n.type || 'skill' },
        position: { x: (i % 5) * 180, y: Math.floor(i / 5) * 120 },
      }
    })
    const edges = (graph.edges || [])
      .map((e: any, i: number) => {
        const source = nodeIndex.get(e.from)
        const target = nodeIndex.get(e.to)
        if (source === undefined || target === undefined) return null
        return { id: String(i), source, target }
      })
      .filter(Boolean)
    return { nodes, edges }
  }, [graph])

  const clearEvents = useCallback(() => { setEvents([]); setError(null) }, [])

  const ingested = useMemo(() => {
    const last = [...events].reverse().find(
      (e) => e?.type === 'skill_complete' && e?.skill === 'doc_ingest'
    )
    return last?.payload?.result || null
  }, [events])

  const ollama = useMemo(() => {
    const last = [...events].reverse().find(
      (e) => e?.type === 'skill_complete' && e?.skill === 'ollama_generate'
    )
    return last?.payload?.result || null
  }, [events])

  const canRun = !isRunning && goal.trim().length > 0 && selectedSkills.length > 0

  const chip = (active: boolean, disabled = false): string => {
    const base = styles.chip
    if (active) return `${base} ${styles.chipActive}`
    if (disabled) return `${base} ${styles.chipDisabled}`
    return base
  }

  return (
    <div className={styles.container}>
      <FilePicker
        open={pickerOpen}
        initialPath={inputPath || libraryPath || projectRoot}
        projectRoot={projectRoot}
        presets={presets}
        onClose={() => setPickerOpen(false)}
        onPick={onPick}
      />

      <div className={styles.header}>
        <h3 className={styles.headerTitle}>UAR Live System</h3>
        <span className={styles.projectRoot}>{projectRoot}</span>
        <button
          onClick={() => setSkillGuideOpen(true)}
          className={styles.skillGuideButton}
          title="View skill documentation"
        >
          📘 Skill Guide
        </button>
      </div>

      {error && (
        <div className={styles.errorBox}>
          <strong>Error:</strong> {error.message}
          {error.code && <span className={styles.errorCode}>[{error.code}]</span>}
          {error.requestId && <span className={styles.errorCode}>req: {error.requestId}</span>}
          <button onClick={() => setError(null)} className={styles.dismissButton}>Dismiss</button>
          <button onClick={() => { navigator.clipboard.writeText(JSON.stringify(error, null, 2)).catch(() => {}) }} className={styles.copyButton}>Copy</button>
        </div>
      )}

      {/* DOCUMENTS */}
      <div className={styles.box}>
        <div className={styles.sectionHeader}>
          <strong className={styles.sectionTitle}>Documents</strong>
          <span className={styles.sectionInfo}>
            library: {libraryPath}
          </span>
          <button
            onClick={() => setPickerOpen(true)}
            disabled={isRunning}
            className={styles.pickButton}
            title="Open file picker"
          >📂 Pick…</button>
        </div>

        {/* Drop zone */}
        <div
          onDrop={onDrop}
          onDragOver={onDragOver}
          onDragEnter={onDragOver}
          onDragLeave={onDragLeave}
          onClick={() => fileInputRef.current?.click()}
          className={`${styles.dropZone} ${dragActive ? styles.dropZoneActive : ''}`}
        >
          <div className={styles.dropZoneIcon}>{dragActive ? '⬇️' : '📥'}</div>
          <div className={styles.dropZoneText}>
            {dragActive ? 'Drop here to add to library' : 'Drop files here, or click to choose'}
          </div>
          <div className={styles.dropZoneSubtext}>
            PDFs · DOCX · XLSX · IPYNB · Parquet · Markdown · Code · Data · max 50MB each
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            aria-label="Upload files to library"
            className={styles.hiddenInput}
            onChange={(e: any) => {
              if (e.target.files?.length) uploadFiles(e.target.files)
              e.target.value = ''
            }}
          />
        </div>
        {uploadMsg && <div className={styles.uploadMessage}>{uploadMsg}</div>}

        {/* Library list */}
        <div className={styles.presetsContainer}>
          <div className={styles.label}>
            📚 Library ({library.length}{libBusy && ' · refreshing…'})
            <button onClick={refreshLibrary} className={styles.refreshButton}>↻</button>
            {libraryPath && (
              <button onClick={() => onPick(libraryPath)} className={styles.useAllButton} title="Use whole library as input_path">
                use all
              </button>
            )}
          </div>
          {library.length === 0 ? (
            <div className={styles.emptyLibrary}>(empty — drop files above)</div>
          ) : (
            <div className={styles.libraryList}>
              {library.map((f) => (
                <div key={f.path}
                  className={`${styles.libraryItem} ${inputPath === f.path ? styles.libraryItemSelected : ''}`}
                >
                  <span className={styles.libraryItemName} onClick={() => onPick(f.path)} title={f.path}>
                    📄 {f.name}
                  </span>
                  <span className={styles.libraryItemSize}>{human(f.size)}</span>
                  <button onClick={() => deleteLibFile(f.name)} disabled={isRunning} className={styles.deleteButton} title="Delete">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className={styles.presetsContainer}>
          <div className={styles.label}>Presets</div>
          {presets.length === 0 && <span className={styles.loadingText}>(loading…)</span>}
          {presets.map((p) => (
            <button key={p.path} disabled={isRunning} onClick={() => onPick(p.path)} className={chip(inputPath === p.path, isRunning)} title={p.path}>
              {p.name}
            </button>
          ))}
        </div>

        {recent.length > 0 && (
          <div className={styles.recentContainer}>
            <div className={styles.label}>
              Recent
              <button onClick={clearRecent} className={styles.clearButton}>clear</button>
            </div>
            {recent.map((p) => (
              <button key={p} disabled={isRunning} onClick={() => onPick(p)} className={chip(inputPath === p, isRunning)} title={p}>
                {p.length > 40 ? '…' + p.slice(-40) : p}
              </button>
            ))}
          </div>
        )}

        <div>
          <label className={styles.label}>input_path</label>
          <div className={styles.inputGroup}>
            <input
              value={inputPath}
              onChange={(e: any) => setInputPath(e.target.value)}
              placeholder="(none — doc_ingest will warn)"
              disabled={isRunning}
              className={styles.input}
            />
            <button onClick={copyPath} disabled={!inputPath} className={styles.iconButton} title="Copy path">📋</button>
            <button onClick={() => setInputPath('')} disabled={!inputPath || isRunning} className={styles.iconButton} title="Clear">✕</button>
          </div>
        </div>
      </div>

      {/* GOAL + SKILLS */}
      <div className={styles.box}>
        <div className={styles.marginBottom12}>
          <label className={styles.label}>Goal</label>
          <input
            value={goal}
            onChange={(e: any) => setGoal(e.target.value)}
            placeholder="What do you want to accomplish?"
            disabled={isRunning}
            className={`${styles.input} ${styles.widthFull}`}
          />
          <datalist id="goal-templates">
            {GOAL_TEMPLATES.map((g) => <option key={g} value={g} />)}
          </datalist>
          <div className={styles.marginTop4}>
            {GOAL_TEMPLATES.map((g) => (
              <button key={g} onClick={() => setGoal(g)} disabled={isRunning} className={`${chip(goal === g, isRunning)} ${styles.smallButton}`}>
                {g.length > 30 ? g.slice(0, 30) + '…' : g}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label className={styles.label}>Skills</label>
          <div>
            {AVAILABLE_SKILLS.map((s) => (
              <button key={s.id} onClick={() => toggleSkill(s.id)} disabled={isRunning} title={s.desc} className={chip(selectedSkills.includes(s.id), isRunning)}>
                {selectedSkills.includes(s.id) ? '✓ ' : ''}{s.label}
              </button>
            ))}
          </div>
          <div className={styles.orderText}>
            Order: {selectedSkills.length ? selectedSkills.join(' → ') : '(none)'}
          </div>

          {/* Recipes */}
          <div className={styles.presetsContainer}>
            <label className={styles.label}>Recipes</label>
            <div className={styles.recipeContainer}>
              {RECIPES.map((r) => (
                <button key={r.id}
                  title={r.hint}
                  onClick={() => setSelectedSkills([...r.skills])}
                  className={styles.presetButton}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {/* Advanced overrides */}
          <div className={styles.advancedOverrides}>
            <label className={`${styles.label} ${styles.marginBottom6}`}>Advanced</label>
            <div className={styles.advancedOverridesContainer}>
              {selectedSkills.includes('graphrag_query') && (
                <label className={styles.advancedOverride}>
                  GraphRAG method:
                  <select value={graphragMethod} onChange={(e) => setGraphragMethod(e.target.value as any)} className={styles.advancedOverrideSelect}>
                    <option value="local">local (entity)</option>
                    <option value="global">global (thematic)</option>
                  </select>
                </label>
              )}
              {selectedSkills.includes('ollama_generate') && (
                <label className={styles.advancedOverride}>
                  Ollama model:
                  <input
                    value={ollamaModel}
                    onChange={(e) => setOllamaModel(e.target.value)}
                    placeholder="e.g. llama3.2"
                    className={styles.advancedOverrideInput}
                  />
                </label>
              )}
              {(selectedSkills.includes('autonomi_upload') || selectedSkills.includes('autonomi_download') || selectedSkills.includes('autonomi_status')) && (
                <>
                  <label className={styles.advancedOverride}>
                    Autonomi key:
                    <input
                      type="password"
                      value={autonomiKey}
                      onChange={(e) => setAutonomiKey(e.target.value)}
                      placeholder="private key"
                      className={styles.advancedOverrideInput}
                    />
                  </label>
                  <label className={styles.advancedOverride}>
                    Autonomi network:
                    <select value={autonomiNetwork} onChange={(e) => setAutonomiNetwork(e.target.value as any)} className={styles.advancedOverrideSelect}>
                      <option value="testnet">testnet</option>
                      <option value="mainnet">mainnet</option>
                    </select>
                  </label>
                  {selectedSkills.includes('autonomi_upload') && (
                    <label className={styles.advancedOverride}>
                      Public:
                      <input
                        type="checkbox"
                        checked={autonomiPublic}
                        onChange={(e) => setAutonomiPublic(e.target.checked)}
                        className={styles.advancedOverrideCheckbox}
                      />
                    </label>
                  )}
                  {selectedSkills.includes('autonomi_download') && (
                    <label className={styles.advancedOverride}>
                      Autonomi address:
                      <input
                        value={autonomiAddress}
                        onChange={(e) => setAutonomiAddress(e.target.value)}
                        placeholder="address from upload"
                        className={styles.advancedOverrideInput}
                      />
                    </label>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* RUN */}
      <div className={styles.presetsContainer}>
        <button
          onClick={runStream}
          disabled={!canRun}
          className={styles.runButton}
        >
          {isRunning ? '⏳ Running…' : '▶ Run Stream'}
        </button>
        {isRunning && (
          <button
            onClick={stopStream}
            className={styles.stopButton}
          >
            ⏹ Stop
          </button>
        )}
        {isRunning && (
          <span className={styles.runStatus}>
            {currentSkill} • {Math.floor((Date.now() - startTime) / 1000)}s
          </span>
        )}
        <button onClick={clearEvents} className={styles.clearButton}>
          Clear Events
        </button>
      </div>

      <div className={styles.statusText}>
        Status: {isRunning ? 'Running' : 'Idle'} · Events: {events.length} · Graph: {graph ? 'Loaded' : 'None'}
        {ingested && <> · Ingested: {ingested.document_count ?? (ingested.documents?.length ?? 0)} docs</>}
      </div>

      {ingested && (
        <div className={styles.box}>
          <strong>Ingested documents</strong>
          {ingested.warning && <div className={styles.ingestedWarning}>{ingested.warning}</div>}
          <div className={styles.ingestedList}>
            {(ingested.documents || []).map((d: any, i: number) => (
              <div key={i} className={styles.ingestedItem}>
                <div className={styles.ingestedItemName}>{d.path || d.name || `#${i}`}</div>
                {d.error ? <div className={styles.ingestedItemError}>error: {d.error}</div>
                  : <div className={styles.ingestedItemInfo}>{d.size ? human(d.size) : ''}{d.type ? ` · ${d.type}` : ''}</div>}
              </div>
            ))}
            {(!ingested.documents || ingested.documents.length === 0) && !ingested.warning && (
              <div className={styles.ingestedEmpty}>(no documents)</div>
            )}
          </div>
        </div>
      )}

      {ollama && (
        <div className={styles.box}>
          <div className={styles.ollamaResponseHeader}>
            <strong>🦙 Ollama response</strong>
            <span className={styles.ollamaResponseInfo}>
              {ollama.model} · status: {ollama.status}
              {typeof ollama.documents_used === 'number' && <> · {ollama.documents_used} docs</>}
              {typeof ollama.context_chars === 'number' && <> · {ollama.context_chars} chars context</>}
            </span>
          </div>
          {ollama.error && <div className={styles.ollamaError}>Error: {ollama.error}</div>}
          {ollama.response && (
            <pre className={styles.ollamaResponse}>
              {ollama.response}
            </pre>
          )}
        </div>
      )}

      <div className={styles.box}>
        <strong>Events ({events.length})</strong>
        <div className={styles.eventsContainer}>
          <pre className={styles.eventsPre}>
            {JSON.stringify(events.slice(-50), null, 2)}
          </pre>
        </div>
      </div>

      <div className={styles.graphContainer}>
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
        </ReactFlow>
      </div>

      {skillGuideOpen && (
        <div
          onClick={() => setSkillGuideOpen(false)}
          className={styles.skillGuideModalOverlay}
        >
          <div
            onClick={(e: any) => e.stopPropagation()}
            className={styles.skillGuideModalContent}
          >
            <div className={styles.skillGuideModalHeader}>
              <strong>Skill Guide</strong>
              <button
                onClick={() => setSkillGuideOpen(false)}
                className={styles.modalCloseButton}
              >
                ✕
              </button>
            </div>
            <div className={styles.skillGuideModalBody}>
              <SkillGuide />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
