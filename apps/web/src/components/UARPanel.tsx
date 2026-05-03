import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'

const MAX_EVENTS = 1000
const RECENT_KEY = 'uar.recentPaths'
const RECENT_MAX = 8

const AVAILABLE_SKILLS = [
  { id: 'doc_ingest',     label: 'doc_ingest',     desc: 'Read files from input_path' },
  { id: 'dependency_map', label: 'dependency_map', desc: 'Build dependency graph' },
  { id: 'section_sum',    label: 'section_sum',    desc: 'Summarize sections' },
  { id: 'sum_review',     label: 'sum_review',     desc: 'Final review of run' },
]

type Preset = { name: string; path: string }
type BrowseEntry = { name: string; path: string; size: number; ext: string; is_dir: boolean }
type BrowseResult = {
  path: string
  is_dir: boolean
  file_count: number
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

export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [inputPath, setInputPath] = useState('')
  const [selectedSkills, setSelectedSkills] = useState<string[]>(['doc_ingest', 'dependency_map', 'sum_review'])
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

  // Document management
  const [presets, setPresets] = useState<Preset[]>([])
  const [projectRoot, setProjectRoot] = useState<string>('')
  const [recent, setRecent] = useState<string[]>(() => {
    try { return JSON.parse(localStorage.getItem(RECENT_KEY) || '[]') } catch { return [] }
  })
  const [browse, setBrowse] = useState<BrowseResult | null>(null)
  const [browseBusy, setBrowseBusy] = useState(false)
  const [browseError, setBrowseError] = useState<string | null>(null)

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

  // Load presets once
  useEffect(() => {
    fetch('/api/uar/docs/presets')
      .then((r) => r.json())
      .then((d) => {
        setPresets(d.presets || [])
        setProjectRoot(d.project_root || '')
      })
      .catch(() => {})
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

  const doBrowse = async (pathArg?: string) => {
    const target = (pathArg ?? inputPath).trim()
    if (!target) {
      setBrowseError('Enter a path first')
      return
    }
    setBrowseBusy(true)
    setBrowseError(null)
    setBrowse(null)
    try {
      const r = await fetch(`/api/uar/docs/browse?path=${encodeURIComponent(target)}&limit=200`)
      const j = await r.json()
      if (!r.ok) {
        setBrowseError(j.message || j.error || `HTTP ${r.status}`)
      } else {
        setBrowse(j)
        pushRecent(target)
      }
    } catch (e: any) {
      setBrowseError(e?.message || 'Browse failed')
    } finally {
      setBrowseBusy(false)
    }
  }

  const toggleSkill = (id: string) => {
    setSelectedSkills((prev) =>
      prev.includes(id) ? prev.filter((s) => s !== id) : [...prev, id]
    )
  }

  const runStream = useCallback(async () => {
    setEvents([])
    setGraph(null)
    setError(null)
    setIsRunning(true)
    eventCountRef.current = 0
    abortControllerRef.current = new AbortController()

    const body: any = { goal, skills: selectedSkills }
    if (inputPath.trim()) {
      body.input_path = inputPath.trim()
      pushRecent(inputPath.trim())
    }

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
                setError(`Event limit reached (${MAX_EVENTS}).`)
                setIsRunning(false)
                return
              }
              setEvents((prev) => {
                const next = prev.length >= MAX_EVENTS ? prev.slice(1) : prev
                return [...next, json]
              })
              if (json.type === 'orchestration_plan' && json.payload?.graph) setGraph(json.payload.graph)
              if (json.run?.final_context?.dependency_map) setGraph(json.run.final_context.dependency_map)
              if (json.type === 'error' && json.error) setError(json.error)
            } catch (parseError) {
              console.error('Failed to parse SSE data:', parseError, 'Data:', line)
              setError('Failed to parse server response')
            }
          }
        }
      }
    } catch (err) {
      if (err instanceof Error && err.name === 'AbortError') {
        console.log('Stream aborted by user')
      } else {
        console.error('Stream error:', err)
        setError(err instanceof Error ? err.message : 'Unknown error occurred')
      }
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

  const clearEvents = useCallback(() => {
    setEvents([])
    setError(null)
  }, [])

  // Ingested documents (from doc_ingest skill_complete payload)
  const ingested = useMemo(() => {
    const last = [...events].reverse().find(
      (e) => e?.type === 'skill_complete' && e?.skill === 'doc_ingest'
    )
    return last?.payload?.result || null
  }, [events])

  const canRun = !isRunning && goal.trim().length > 0 && selectedSkills.length > 0

  const box: any = { border: '1px solid #dee2e6', borderRadius: 4, padding: 12, marginBottom: 16, background: '#fff' }
  const label: any = { display: 'block', fontSize: 12, color: '#555', marginBottom: 4 }
  const chip = (active: boolean): any => ({
    display: 'inline-flex', alignItems: 'center', gap: 6,
    padding: '4px 10px', margin: '2px 4px 2px 0',
    border: '1px solid #ccc', borderRadius: 999,
    background: active ? '#e7f1ff' : '#fff',
    fontFamily: 'monospace', fontSize: 12, cursor: isRunning ? 'not-allowed' : 'pointer',
  })

  return (
    <div style={{ padding: 20, maxWidth: 1200, margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
      <h3 style={{ marginTop: 0 }}>UAR Live System</h3>

      {error && (
        <div style={{ background: '#fee', border: '1px solid #fcc', padding: 10, marginBottom: 16, borderRadius: 4 }}>
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)} style={{ marginLeft: 10, padding: '2px 8px' }}>Dismiss</button>
        </div>
      )}

      {/* ========== DOCUMENT MANAGEMENT ========== */}
      <div style={box}>
        <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', marginBottom: 8 }}>
          <strong>Documents</strong>
          <span style={{ fontSize: 11, color: '#888' }}>
            project_root: <code>{projectRoot || '(loading)'}</code>
          </span>
        </div>

        {/* Presets */}
        <div style={{ marginBottom: 8 }}>
          <div style={label}>Presets</div>
          {presets.length === 0 && <span style={{ fontSize: 12, color: '#888' }}>(none found)</span>}
          {presets.map((p) => (
            <button
              key={p.path}
              disabled={isRunning}
              onClick={() => { setInputPath(p.path); doBrowse(p.path) }}
              style={chip(inputPath === p.path)}
              title={p.path}
            >
              {p.name}
            </button>
          ))}
        </div>

        {/* Recent */}
        {recent.length > 0 && (
          <div style={{ marginBottom: 8 }}>
            <div style={label}>
              Recent
              <button onClick={clearRecent} style={{ marginLeft: 8, fontSize: 11, padding: '0 6px' }}>clear</button>
            </div>
            {recent.map((p) => (
              <button
                key={p}
                disabled={isRunning}
                onClick={() => { setInputPath(p); doBrowse(p) }}
                style={chip(inputPath === p)}
                title={p}
              >
                {p.length > 40 ? '…' + p.slice(-40) : p}
              </button>
            ))}
          </div>
        )}

        {/* Path + Browse */}
        <div style={{ marginBottom: 8 }}>
          <label style={label}>input_path</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <input
              value={inputPath}
              onChange={(e: any) => setInputPath(e.target.value)}
              onKeyDown={(e: any) => { if (e.key === 'Enter') doBrowse() }}
              placeholder="e.g. docs  or  /abs/path/to/folder"
              disabled={isRunning}
              style={{ flex: 1, padding: 8, border: '1px solid #ccc', borderRadius: 4, fontFamily: 'monospace' }}
            />
            <button
              onClick={() => doBrowse()}
              disabled={browseBusy || isRunning || !inputPath.trim()}
              style={{ padding: '8px 14px', background: '#17a2b8', color: '#fff', border: 'none', borderRadius: 4 }}
            >
              {browseBusy ? 'Browsing…' : 'Browse'}
            </button>
            <button
              onClick={() => { setInputPath(''); setBrowse(null); setBrowseError(null) }}
              disabled={isRunning}
              style={{ padding: '8px 14px', background: '#6c757d', color: '#fff', border: 'none', borderRadius: 4 }}
            >
              Clear
            </button>
          </div>
        </div>

        {/* Browse result */}
        {browseError && (
          <div style={{ color: '#b00', fontSize: 13, marginTop: 6 }}>Browse error: {browseError}</div>
        )}
        {browse && (
          <div style={{ marginTop: 8, border: '1px solid #e3e5e8', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{ padding: '6px 10px', background: '#f8f9fa', fontSize: 12 }}>
              <strong>{browse.file_count}</strong> files · <strong>{human(browse.total_bytes)}</strong>
              {browse.truncated && <span style={{ color: '#b00' }}> · truncated</span>}
              <span style={{ marginLeft: 10, color: '#666' }}>
                {Object.entries(browse.by_extension).sort((a, b) => b[1] - a[1])
                  .slice(0, 6).map(([k, v]) => `${k}:${v}`).join('  ')}
              </span>
            </div>
            <div style={{ maxHeight: 180, overflow: 'auto', fontSize: 12, fontFamily: 'monospace' }}>
              {browse.entries.map((e) => (
                <div key={e.path} style={{ display: 'flex', justifyContent: 'space-between', padding: '2px 10px', borderBottom: '1px solid #f1f3f5' }}>
                  <span>{e.name}</span>
                  <span style={{ color: '#888' }}>{human(e.size)}</span>
                </div>
              ))}
              {browse.entries.length === 0 && <div style={{ padding: 10, color: '#888' }}>(empty)</div>}
            </div>
          </div>
        )}
      </div>

      {/* ========== GOAL + SKILLS ========== */}
      <div style={box}>
        <div style={{ marginBottom: 10 }}>
          <label style={label}>Goal</label>
          <input
            value={goal}
            onChange={(e: any) => setGoal(e.target.value)}
            placeholder="e.g. Summarize the project"
            disabled={isRunning}
            style={{ padding: 8, width: '100%', border: '1px solid #ccc', borderRadius: 4 }}
          />
        </div>
        <div>
          <label style={label}>Skills (pipeline order)</label>
          <div>
            {AVAILABLE_SKILLS.map((s) => (
              <button
                key={s.id}
                onClick={() => toggleSkill(s.id)}
                disabled={isRunning}
                title={s.desc}
                style={chip(selectedSkills.includes(s.id))}
              >
                {selectedSkills.includes(s.id) ? '✓ ' : ''}{s.label}
              </button>
            ))}
          </div>
          <div style={{ fontSize: 11, color: '#888', marginTop: 4 }}>
            Order: {selectedSkills.length ? selectedSkills.join(' → ') : '(none)'}
          </div>
        </div>
      </div>

      {/* ========== RUN CONTROLS ========== */}
      <div style={{ marginBottom: 16 }}>
        <button
          onClick={runStream}
          disabled={!canRun}
          style={{
            padding: '8px 16px', marginRight: 10,
            background: !canRun ? '#ccc' : '#007bff', color: '#fff',
            border: 'none', borderRadius: 4,
            cursor: !canRun ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? 'Running...' : 'Run Stream'}
        </button>
        {isRunning && (
          <button onClick={stopStream} style={{ padding: '8px 16px', marginRight: 10, background: '#dc3545', color: '#fff', border: 'none', borderRadius: 4 }}>
            Stop
          </button>
        )}
        <button onClick={clearEvents} style={{ padding: '8px 16px', background: '#6c757d', color: '#fff', border: 'none', borderRadius: 4 }}>
          Clear Events
        </button>
      </div>

      <div style={{ marginBottom: 16, fontSize: 13, color: '#666' }}>
        Status: {isRunning ? 'Running' : 'Idle'} · Events: {events.length} · Graph: {graph ? 'Loaded' : 'None'}
        {ingested && <> · Ingested: {ingested.document_count ?? (ingested.documents?.length ?? 0)} docs</>}
      </div>

      {/* ========== INGESTED DOCS RESULT ========== */}
      {ingested && (
        <div style={box}>
          <strong>Ingested documents</strong>
          {ingested.warning && <div style={{ color: '#a66', fontSize: 12, marginTop: 4 }}>{ingested.warning}</div>}
          <div style={{ maxHeight: 220, overflow: 'auto', marginTop: 8, fontSize: 12, fontFamily: 'monospace' }}>
            {(ingested.documents || []).map((d: any, i: number) => (
              <div key={i} style={{ padding: '4px 6px', borderBottom: '1px solid #f1f3f5' }}>
                <div style={{ fontWeight: 600 }}>{d.path || d.name || `#${i}`}</div>
                {d.error ? (
                  <div style={{ color: '#b00' }}>error: {d.error}</div>
                ) : (
                  <div style={{ color: '#666' }}>{d.size ? human(d.size) : ''}{d.type ? ` · ${d.type}` : ''}</div>
                )}
              </div>
            ))}
            {(!ingested.documents || ingested.documents.length === 0) && !ingested.warning && (
              <div style={{ color: '#888' }}>(no documents)</div>
            )}
          </div>
        </div>
      )}

      {/* ========== EVENT LOG ========== */}
      <div style={box}>
        <strong>Events ({events.length})</strong>
        <div style={{ background: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: 4, maxHeight: 280, overflow: 'auto', marginTop: 6 }}>
          <pre style={{ margin: 0, padding: 10, fontSize: 12 }}>
            {JSON.stringify(events.slice(-50), null, 2)}
          </pre>
        </div>
      </div>

      {/* ========== GRAPH ========== */}
      <div style={{ height: 400, border: '1px solid #dee2e6', borderRadius: 4 }}>
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
        </ReactFlow>
      </div>
    </div>
  )
}
