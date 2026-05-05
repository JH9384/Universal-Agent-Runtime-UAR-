import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'

const MAX_EVENTS = 1000
const RECENT_KEY = 'uar.recentPaths'
const RECENT_MAX = 8

const AVAILABLE_SKILLS = [
  { id: 'doc_ingest',     label: 'doc_ingest',     desc: 'Read files from input_path (.md .txt .py .ts .json …)' },
  { id: 'dependency_map', label: 'dependency_map', desc: 'Build a dependency graph between artifacts' },
  { id: 'section_sum',    label: 'section_sum',    desc: 'Summarize document sections' },
  { id: 'sum_review',     label: 'sum_review',     desc: 'Final review of pipeline outputs' },
  { id: 'ollama_generate', label: 'ollama_generate', desc: 'Send goal + ingested docs to local Ollama model (requires Ollama running)' },
  { id: 'graphrag_index',  label: 'graphrag_index',  desc: 'Build a GraphRAG knowledge graph over input_path (slow; one-time)' },
  { id: 'graphrag_query',  label: 'graphrag_query',  desc: 'Query the GraphRAG index. Metadata: graphrag_method=local|global' },
  { id: 'autonomi_upload',   label: 'autonomi_upload',   desc: 'Upload file/dir to Autonomi decentralized storage (requires autonomi package + wallet)' },
  { id: 'autonomi_download', label: 'autonomi_download', desc: 'Download a file from Autonomi by address (requires autonomi package)' },
  { id: 'autonomi_status',   label: 'autonomi_status',   desc: 'Check Autonomi client and wallet status' },
  { id: 'alm_analyze',      label: 'alm_analyze',      desc: 'Analyze formal grammar specifications (BNF, EBNF) with ALM (requires ALM service)' },
  { id: 'alm_generate',     label: 'alm_generate',     desc: 'Generate token sequences from a prefix using ALM (requires ALM service)' },
  { id: 'alm_verify',       label: 'alm_verify',       desc: 'Validate text against ALM grammar (requires ALM service)' },
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
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)',
        display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000,
      }}
    >
      <div
        onClick={(e: any) => e.stopPropagation()}
        style={{
          width: 'min(820px, 92vw)', maxHeight: '86vh', background: '#fff',
          borderRadius: 8, boxShadow: '0 10px 40px rgba(0,0,0,0.25)',
          display: 'flex', flexDirection: 'column', overflow: 'hidden',
        }}
      >
        {/* Header */}
        <div style={{ padding: '12px 16px', borderBottom: '1px solid #e3e5e8', display: 'flex', alignItems: 'center', gap: 10 }}>
          <strong>Pick a folder or file</strong>
          <span style={{ fontSize: 11, color: '#888' }}>(must be within PROJECT_ROOT)</span>
          <button onClick={onClose} style={{ marginLeft: 'auto', padding: '4px 10px' }}>✕</button>
        </div>

        {/* Presets row */}
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #f1f3f5', display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          <span style={{ fontSize: 12, color: '#666', alignSelf: 'center' }}>Quick:</span>
          <button onClick={() => load(projectRoot)} style={{ padding: '2px 10px', fontSize: 12 }}>/ root</button>
          {presets.map((p) => (
            <button key={p.path} onClick={() => load(p.path)} style={{ padding: '2px 10px', fontSize: 12 }}>
              {p.name}
            </button>
          ))}
        </div>

        {/* Breadcrumbs + nav */}
        <div style={{ padding: '8px 16px', background: '#fafbfc', borderBottom: '1px solid #f1f3f5', fontSize: 12, display: 'flex', flexWrap: 'wrap', alignItems: 'center', gap: 4 }}>
          <button
            onClick={() => data?.parent && load(data.parent)}
            disabled={!data?.parent || busy}
            title="Parent"
            style={{ padding: '2px 8px' }}
          >⬆</button>
          <button onClick={() => data && load(data.path, true)} disabled={busy || !data?.is_dir} style={{ padding: '2px 8px' }} title="Recursive listing">⤓</button>
          <button onClick={() => data && load(data.path)} disabled={busy} style={{ padding: '2px 8px' }} title="Reload">⟳</button>
          <span style={{ marginLeft: 6, color: '#666' }}>
            {breadcrumbs.map((b, i) => (
              <span key={b.path}>
                <a
                  onClick={() => load(b.path)}
                  style={{ cursor: 'pointer', color: '#0366d6', textDecoration: 'underline' }}
                >{b.label}</a>
                {i < breadcrumbs.length - 1 && <span style={{ color: '#aaa' }}> / </span>}
              </span>
            ))}
          </span>
        </div>

        {/* Filter + manual path */}
        <div style={{ padding: '8px 16px', borderBottom: '1px solid #f1f3f5', display: 'flex', gap: 8 }}>
          <input
            placeholder="Filter (filename contains…)"
            value={filter}
            onChange={(e: any) => setFilter(e.target.value)}
            style={{ flex: 1, padding: 6, border: '1px solid #ccc', borderRadius: 4, fontSize: 13 }}
          />
          <input
            placeholder="Or type a path and press Enter"
            value={path}
            onChange={(e: any) => setPath(e.target.value)}
            onKeyDown={(e: any) => { if (e.key === 'Enter') load(path) }}
            style={{ flex: 2, padding: 6, border: '1px solid #ccc', borderRadius: 4, fontSize: 13, fontFamily: 'monospace' }}
          />
        </div>

        {/* Body */}
        <div style={{ flex: 1, overflow: 'auto', minHeight: 240 }}>
          {err && <div style={{ padding: 12, color: '#b00', fontSize: 13 }}>Error: {err}</div>}
          {busy && <div style={{ padding: 12, color: '#666', fontSize: 13 }}>Loading…</div>}
          {!busy && !err && data && (
            <>
              <div style={{ padding: '4px 16px', fontSize: 11, color: '#666', background: '#fcfcfd' }}>
                <strong>{data.dir_count}</strong> dirs · <strong>{data.file_count}</strong> files
                {data.total_bytes > 0 && <> · <strong>{human(data.total_bytes)}</strong></>}
                {data.truncated && <span style={{ color: '#b00' }}> · truncated</span>}
                {data.recursive && <span style={{ color: '#17a2b8' }}> · recursive</span>}
                {Object.keys(data.by_extension).length > 0 && (
                  <span style={{ marginLeft: 8 }}>
                    {Object.entries(data.by_extension).sort((a, b) => b[1] - a[1])
                      .slice(0, 8).map(([k, v]) => `${k}:${v}`).join('  ')}
                  </span>
                )}
              </div>
              <div style={{ fontFamily: 'monospace', fontSize: 13 }}>
                {filtered.map((e) => (
                  <div
                    key={e.path}
                    onClick={() => e.is_dir ? load(e.path) : onPick(e.path)}
                    onDoubleClick={() => onPick(e.path)}
                    style={{
                      display: 'flex', justifyContent: 'space-between',
                      padding: '4px 16px', borderBottom: '1px solid #f5f6f7',
                      cursor: 'pointer', background: e.is_dir ? '#fafbff' : '#fff',
                    }}
                    title={e.is_dir ? 'Click to open' : 'Click to select this file'}
                    onMouseEnter={(ev: any) => ev.currentTarget.style.background = '#eef2ff'}
                    onMouseLeave={(ev: any) => ev.currentTarget.style.background = e.is_dir ? '#fafbff' : '#fff'}
                  >
                    <span>
                      {e.is_dir ? '📁 ' : '📄 '}
                      <span style={{ fontWeight: e.is_dir ? 600 : 400 }}>{e.name}</span>
                      {e.is_dir && '/'}
                    </span>
                    <span style={{ color: '#888' }}>{e.is_dir ? '' : human(e.size)}</span>
                  </div>
                ))}
                {filtered.length === 0 && <div style={{ padding: 16, color: '#888' }}>(no entries)</div>}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '10px 16px', borderTop: '1px solid #e3e5e8', display: 'flex', gap: 8, alignItems: 'center' }}>
          <span style={{ fontSize: 12, color: '#666', flex: 1, fontFamily: 'monospace', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            Selected: {data?.path || '(none)'}
          </span>
          <button onClick={onClose} style={{ padding: '6px 14px' }}>Cancel</button>
          <button
            onClick={() => data && onPick(data.path)}
            disabled={!data}
            style={{ padding: '6px 14px', background: '#007bff', color: '#fff', border: 'none', borderRadius: 4 }}
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

  const box: any = { border: '1px solid #dee2e6', borderRadius: 6, padding: 14, marginBottom: 16, background: '#fff' }
  const label: any = { display: 'block', fontSize: 12, color: '#555', marginBottom: 4 }
  const chip = (active: boolean, disabled = false): any => ({
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '4px 10px', margin: '2px 4px 2px 0',
    border: '1px solid ' + (active ? '#3a7bd5' : '#ccc'), borderRadius: 999,
    background: active ? '#e7f1ff' : '#fff', color: active ? '#0b3d91' : '#222',
    fontFamily: 'monospace', fontSize: 12,
    cursor: disabled ? 'not-allowed' : 'pointer',
  })

  return (
    <div style={{ padding: 20, maxWidth: 1200, margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
      <FilePicker
        open={pickerOpen}
        initialPath={inputPath || libraryPath || projectRoot}
        projectRoot={projectRoot}
        presets={presets}
        onClose={() => setPickerOpen(false)}
        onPick={onPick}
      />

      <div style={{ display: 'flex', alignItems: 'baseline', gap: 12, marginBottom: 12 }}>
        <h3 style={{ margin: 0 }}>UAR Live System</h3>
        <span style={{ fontSize: 11, color: '#888', fontFamily: 'monospace' }}>{projectRoot}</span>
      </div>

      {error && (
        <div style={{ background: '#fee', border: '1px solid #fcc', padding: 10, marginBottom: 16, borderRadius: 4 }}>
          <strong>Error:</strong> {error.message}
          {error.code && <span style={{ marginLeft: 8, fontSize: 11, color: '#888' }}>[{error.code}]</span>}
          {error.requestId && <span style={{ marginLeft: 8, fontSize: 11, color: '#888' }}>req: {error.requestId}</span>}
          <button onClick={() => setError(null)} style={{ marginLeft: 10, padding: '2px 8px' }}>Dismiss</button>
          <button onClick={() => { navigator.clipboard.writeText(JSON.stringify(error, null, 2)).catch(() => {}) }} style={{ marginLeft: 6, padding: '2px 8px', fontSize: 11 }}>Copy</button>
        </div>
      )}

      {/* DOCUMENTS */}
      <div style={box}>
        <div style={{ display: 'flex', alignItems: 'center', marginBottom: 10 }}>
          <strong>Documents</strong>
          <span style={{ fontSize: 11, color: '#888', marginLeft: 12, fontFamily: 'monospace' }}>
            library: {libraryPath}
          </span>
          <button
            onClick={() => setPickerOpen(true)}
            disabled={isRunning}
            style={{ marginLeft: 'auto', padding: '6px 14px', background: '#0d6efd', color: '#fff', border: 'none', borderRadius: 4, fontWeight: 600 }}
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
          style={{
            border: `2px dashed ${dragActive ? '#0d6efd' : '#ced4da'}`,
            borderRadius: 6,
            padding: '18px 14px',
            textAlign: 'center',
            background: dragActive ? '#e7f1ff' : '#fafbfc',
            color: '#555',
            cursor: 'pointer',
            transition: 'all .15s',
            marginBottom: 10,
          }}
        >
          <div style={{ fontSize: 24, marginBottom: 4 }}>{dragActive ? '⬇️' : '📥'}</div>
          <div style={{ fontWeight: 600 }}>
            {dragActive ? 'Drop here to add to library' : 'Drop files here, or click to choose'}
          </div>
          <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
            PDFs · DOCX · XLSX · IPYNB · Parquet · Markdown · Code · Data · max 50MB each
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            aria-label="Upload files to library"
            style={{ display: 'none' }}
            onChange={(e: any) => {
              if (e.target.files?.length) uploadFiles(e.target.files)
              e.target.value = ''
            }}
          />
        </div>
        {uploadMsg && <div style={{ fontSize: 12, color: '#0a4', marginBottom: 8 }}>{uploadMsg}</div>}

        {/* Library list */}
        <div style={{ marginBottom: 10 }}>
          <div style={label}>
            📚 Library ({library.length}{libBusy && ' · refreshing…'})
            <button onClick={refreshLibrary} style={{ marginLeft: 8, fontSize: 11, padding: '0 6px' }}>↻</button>
            {libraryPath && (
              <button onClick={() => onPick(libraryPath)} style={{ marginLeft: 4, fontSize: 11, padding: '0 6px' }} title="Use whole library as input_path">
                use all
              </button>
            )}
          </div>
          {library.length === 0 ? (
            <div style={{ fontSize: 12, color: '#888' }}>(empty — drop files above)</div>
          ) : (
            <div style={{ maxHeight: 150, overflow: 'auto', border: '1px solid #eef', borderRadius: 4, fontFamily: 'monospace', fontSize: 12 }}>
              {library.map((f) => (
                <div key={f.path}
                  style={{
                    display: 'flex', alignItems: 'center', gap: 8,
                    padding: '3px 8px', borderBottom: '1px solid #f5f6f7',
                    background: inputPath === f.path ? '#e7f1ff' : '#fff',
                  }}
                >
                  <span style={{ flex: 1, cursor: 'pointer' }} onClick={() => onPick(f.path)} title={f.path}>
                    📄 {f.name}
                  </span>
                  <span style={{ color: '#888' }}>{human(f.size)}</span>
                  <button onClick={() => deleteLibFile(f.name)} disabled={isRunning} style={{ padding: '0 6px', fontSize: 11, color: '#b00' }} title="Delete">✕</button>
                </div>
              ))}
            </div>
          )}
        </div>

        <div style={{ marginBottom: 8 }}>
          <div style={label}>Presets</div>
          {presets.length === 0 && <span style={{ fontSize: 12, color: '#888' }}>(loading…)</span>}
          {presets.map((p) => (
            <button key={p.path} disabled={isRunning} onClick={() => onPick(p.path)} style={chip(inputPath === p.path, isRunning)} title={p.path}>
              {p.name}
            </button>
          ))}
        </div>

        {recent.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={label}>
              Recent
              <button onClick={clearRecent} style={{ marginLeft: 8, fontSize: 11, padding: '0 6px' }}>clear</button>
            </div>
            {recent.map((p) => (
              <button key={p} disabled={isRunning} onClick={() => onPick(p)} style={chip(inputPath === p, isRunning)} title={p}>
                {p.length > 40 ? '…' + p.slice(-40) : p}
              </button>
            ))}
          </div>
        )}

        <div>
          <label style={label}>input_path</label>
          <div style={{ display: 'flex', gap: 6 }}>
            <input
              value={inputPath}
              onChange={(e: any) => setInputPath(e.target.value)}
              placeholder="(none — doc_ingest will warn)"
              disabled={isRunning}
              style={{ flex: 1, padding: 8, border: '1px solid #ccc', borderRadius: 4, fontFamily: 'monospace', fontSize: 13 }}
            />
            <button onClick={copyPath} disabled={!inputPath} style={{ padding: '6px 10px' }} title="Copy path">📋</button>
            <button onClick={() => setInputPath('')} disabled={!inputPath || isRunning} style={{ padding: '6px 10px' }} title="Clear">✕</button>
          </div>
        </div>
      </div>

      {/* GOAL + SKILLS */}
      <div style={box}>
        <div style={{ marginBottom: 12 }}>
          <label style={label}>Goal</label>
          <input
            value={goal}
            onChange={(e: any) => setGoal(e.target.value)}
            placeholder="What should UAR do?"
            disabled={isRunning}
            list="goal-templates"
            style={{ padding: 8, width: '100%', border: '1px solid #ccc', borderRadius: 4 }}
          />
          <datalist id="goal-templates">
            {GOAL_TEMPLATES.map((g) => <option key={g} value={g} />)}
          </datalist>
          <div style={{ marginTop: 4 }}>
            {GOAL_TEMPLATES.map((g) => (
              <button key={g} onClick={() => setGoal(g)} disabled={isRunning} style={{ ...chip(goal === g, isRunning), fontSize: 11, padding: '2px 8px' }}>
                {g.length > 30 ? g.slice(0, 30) + '…' : g}
              </button>
            ))}
          </div>
        </div>

        <div>
          <label style={label}>Skills</label>
          <div>
            {AVAILABLE_SKILLS.map((s) => (
              <button key={s.id} onClick={() => toggleSkill(s.id)} disabled={isRunning} title={s.desc} style={chip(selectedSkills.includes(s.id), isRunning)}>
                {selectedSkills.includes(s.id) ? '✓ ' : ''}{s.label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
            Order: {selectedSkills.length ? selectedSkills.join(' → ') : '(none)'}
          </div>

          {/* Recipes */}
          <div style={{ marginTop: 8 }}>
            <label style={label}>Recipes</label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {RECIPES.map((r) => (
                <button key={r.id}
                  title={r.hint}
                  onClick={() => setSelectedSkills([...r.skills])}
                  style={{ padding: '4px 10px', fontSize: 12, borderRadius: 4, border: '1px solid #ddd', background: '#f8f9fa', cursor: 'pointer' }}
                >
                  {r.label}
                </button>
              ))}
            </div>
          </div>

          {/* Advanced overrides */}
          <div style={{ marginTop: 8, padding: 8, borderRadius: 4, background: '#f8f9fa', border: '1px solid #eee' }}>
            <label style={{ ...label, marginBottom: 6 }}>Advanced</label>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, flexWrap: 'wrap' }}>
              {selectedSkills.includes('graphrag_query') && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#555' }}>
                  GraphRAG method:
                  <select value={graphragMethod} onChange={(e) => setGraphragMethod(e.target.value as any)} style={{ fontSize: 12, padding: 2 }}>
                    <option value="local">local (entity)</option>
                    <option value="global">global (thematic)</option>
                  </select>
                </label>
              )}
              {selectedSkills.includes('ollama_generate') && (
                <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#555' }}>
                  Ollama model:
                  <input type="text"
                    value={ollamaModel}
                    onChange={(e) => setOllamaModel(e.target.value)}
                    placeholder="e.g. qwen2.5:7b"
                    style={{ fontSize: 12, padding: '2px 6px', width: 140 }}
                  />
                </label>
              )}
              {(selectedSkills.includes('autonomi_upload') || selectedSkills.includes('autonomi_download') || selectedSkills.includes('autonomi_status')) && (
                <>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#555' }}>
                    Private key:
                    <input type="password"
                      value={autonomiKey}
                      onChange={(e) => setAutonomiKey(e.target.value)}
                      placeholder="0x... (or set AUTONOMI_PRIVATE_KEY env)"
                      style={{ fontSize: 12, padding: '2px 6px', width: 220 }}
                    />
                  </label>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#555' }}>
                    Network:
                    <select value={autonomiNetwork} onChange={(e) => setAutonomiNetwork(e.target.value as any)} style={{ fontSize: 12, padding: 2 }}>
                      <option value="testnet">testnet</option>
                      <option value="mainnet">mainnet</option>
                    </select>
                  </label>
                  {selectedSkills.includes('autonomi_upload') && (
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#555' }}>
                      <input type="checkbox"
                        checked={autonomiPublic}
                        onChange={(e) => setAutonomiPublic(e.target.checked)}
                        style={{ margin: 0 }}
                      />
                      Public upload
                    </label>
                  )}
                  {selectedSkills.includes('autonomi_download') && (
                    <label style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 12, color: '#555' }}>
                      Address:
                      <input type="text"
                        value={autonomiAddress}
                        onChange={(e) => setAutonomiAddress(e.target.value)}
                        placeholder="autonomi address or data map"
                        style={{ fontSize: 12, padding: '2px 6px', width: 200 }}
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
      <div style={{ marginBottom: 16 }}>
        <button
          onClick={runStream}
          disabled={!canRun}
          style={{
            padding: '10px 20px', marginRight: 10, fontSize: 14, fontWeight: 600,
            background: !canRun ? '#ccc' : '#28a745', color: '#fff',
            border: 'none', borderRadius: 4,
            cursor: !canRun ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? '⏳ Running…' : '▶ Run Stream'}
        </button>
        {isRunning && (
          <button onClick={stopStream} style={{ padding: '10px 16px', marginRight: 10, background: '#dc3545', color: '#fff', border: 'none', borderRadius: 4 }}>
            ■ Stop
          </button>
        )}
        <button onClick={clearEvents} style={{ padding: '10px 16px', background: '#6c757d', color: '#fff', border: 'none', borderRadius: 4 }}>
          Clear Events
        </button>
      </div>

      <div style={{ marginBottom: 16, fontSize: 13, color: '#666' }}>
        Status: {isRunning ? 'Running' : 'Idle'} · Events: {events.length} · Graph: {graph ? 'Loaded' : 'None'}
        {ingested && <> · Ingested: {ingested.document_count ?? (ingested.documents?.length ?? 0)} docs</>}
      </div>

      {ingested && (
        <div style={box}>
          <strong>Ingested documents</strong>
          {ingested.warning && <div style={{ color: '#a66', fontSize: 12, marginTop: 4 }}>{ingested.warning}</div>}
          <div style={{ maxHeight: 220, overflow: 'auto', marginTop: 8, fontSize: 12, fontFamily: 'monospace' }}>
            {(ingested.documents || []).map((d: any, i: number) => (
              <div key={i} style={{ padding: '4px 6px', borderBottom: '1px solid #f1f3f5' }}>
                <div style={{ fontWeight: 600 }}>{d.path || d.name || `#${i}`}</div>
                {d.error ? <div style={{ color: '#b00' }}>error: {d.error}</div>
                  : <div style={{ color: '#666' }}>{d.size ? human(d.size) : ''}{d.type ? ` · ${d.type}` : ''}</div>}
              </div>
            ))}
            {(!ingested.documents || ingested.documents.length === 0) && !ingested.warning && (
              <div style={{ color: '#888' }}>(no documents)</div>
            )}
          </div>
        </div>
      )}

      {ollama && (
        <div style={box}>
          <div style={{ display: 'flex', alignItems: 'baseline', gap: 10 }}>
            <strong>🦙 Ollama response</strong>
            <span style={{ fontSize: 11, color: '#666' }}>
              {ollama.model} · status: {ollama.status}
              {typeof ollama.documents_used === 'number' && <> · {ollama.documents_used} docs</>}
              {typeof ollama.context_chars === 'number' && <> · {ollama.context_chars} chars context</>}
            </span>
          </div>
          {ollama.error && <div style={{ color: '#b00', fontSize: 13, marginTop: 6 }}>Error: {ollama.error}</div>}
          {ollama.response && (
            <pre style={{ marginTop: 8, padding: 10, background: '#f8f9fa', border: '1px solid #e9ecef', borderRadius: 4, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: 13, maxHeight: 360, overflow: 'auto' }}>
              {ollama.response}
            </pre>
          )}
        </div>
      )}

      <div style={box}>
        <strong>Events ({events.length})</strong>
        <div style={{ background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: 4, maxHeight: 280, overflow: 'auto', marginTop: 6 }}>
          <pre style={{ margin: 0, padding: 10, fontSize: 12 }}>
            {JSON.stringify(events.slice(-50), null, 2)}
          </pre>
        </div>
      </div>

      <div style={{ height: 400, border: '1px solid #dee2e6', borderRadius: 4 }}>
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
        </ReactFlow>
      </div>
    </div>
  )
}
