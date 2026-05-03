import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'

const MAX_EVENTS = 1000

const AVAILABLE_SKILLS = [
  { id: 'doc_ingest',      label: 'doc_ingest',      desc: 'Read files from input_path' },
  { id: 'dependency_map',  label: 'dependency_map',  desc: 'Build dependency graph' },
  { id: 'section_sum',     label: 'section_sum',     desc: 'Summarize sections' },
  { id: 'sum_review',      label: 'sum_review',      desc: 'Final review of run' },
]

export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [inputPath, setInputPath] = useState('')
  const [selectedSkills, setSelectedSkills] = useState<string[]>(['doc_ingest', 'dependency_map', 'sum_review'])
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)

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
    if (inputPath.trim()) body.input_path = inputPath.trim()

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
                setError(`Event limit reached (${MAX_EVENTS}). Stream stopped.`)
                setIsRunning(false)
                return
              }
              setEvents((prev) => {
                const next = prev.length >= MAX_EVENTS ? prev.slice(1) : prev
                return [...next, json]
              })
              if (json.type === 'orchestration_plan' && json.payload?.graph) {
                setGraph(json.payload.graph)
              }
              if (json.run?.final_context?.dependency_map) {
                setGraph(json.run.final_context.dependency_map)
              }
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

  const canRun = !isRunning && goal.trim().length > 0 && selectedSkills.length > 0

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto', fontFamily: 'system-ui, sans-serif' }}>
      <h3>UAR Live System</h3>

      {error && (
        <div style={{ backgroundColor: '#fee', border: '1px solid #fcc', padding: '10px', marginBottom: '20px', borderRadius: '4px' }}>
          <strong>Error:</strong> {error}
          <button onClick={() => setError(null)} style={{ marginLeft: '10px', padding: '2px 8px' }}>Dismiss</button>
        </div>
      )}

      {/* Goal */}
      <div style={{ marginBottom: '12px' }}>
        <label style={{ display: 'block', fontSize: '12px', color: '#555', marginBottom: '4px' }}>Goal</label>
        <input
          value={goal}
          onChange={(e: any) => setGoal(e.target.value)}
          placeholder="e.g. Summarize the codebase"
          disabled={isRunning}
          style={{ padding: '8px', width: '100%', maxWidth: '600px', border: '1px solid #ccc', borderRadius: '4px' }}
        />
      </div>

      {/* Input path */}
      <div style={{ marginBottom: '12px' }}>
        <label style={{ display: 'block', fontSize: '12px', color: '#555', marginBottom: '4px' }}>
          input_path (optional — required for doc_ingest to read files; absolute or relative to project root)
        </label>
        <input
          value={inputPath}
          onChange={(e: any) => setInputPath(e.target.value)}
          placeholder="e.g. docs  or  /Users/you/project/docs"
          disabled={isRunning}
          style={{ padding: '8px', width: '100%', maxWidth: '600px', border: '1px solid #ccc', borderRadius: '4px', fontFamily: 'monospace' }}
        />
      </div>

      {/* Skill selector */}
      <div style={{ marginBottom: '16px' }}>
        <label style={{ display: 'block', fontSize: '12px', color: '#555', marginBottom: '6px' }}>Skills (pipeline order)</label>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '12px' }}>
          {AVAILABLE_SKILLS.map((s) => (
            <label
              key={s.id}
              title={s.desc}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                padding: '6px 10px',
                border: '1px solid #ccc',
                borderRadius: '4px',
                background: selectedSkills.includes(s.id) ? '#e7f1ff' : '#fff',
                cursor: isRunning ? 'not-allowed' : 'pointer',
              }}
            >
              <input
                type="checkbox"
                checked={selectedSkills.includes(s.id)}
                onChange={() => toggleSkill(s.id)}
                disabled={isRunning}
              />
              <span style={{ fontFamily: 'monospace', fontSize: '13px' }}>{s.label}</span>
            </label>
          ))}
        </div>
        <div style={{ fontSize: '11px', color: '#888', marginTop: '4px' }}>
          Selected order: {selectedSkills.length ? selectedSkills.join(' → ') : '(none)'}
        </div>
      </div>

      {/* Controls */}
      <div style={{ marginBottom: '20px' }}>
        <button
          onClick={runStream}
          disabled={!canRun}
          style={{
            padding: '8px 16px', marginRight: '10px',
            backgroundColor: !canRun ? '#ccc' : '#007bff',
            color: 'white', border: 'none', borderRadius: '4px',
            cursor: !canRun ? 'not-allowed' : 'pointer',
          }}
        >
          {isRunning ? 'Running...' : 'Run Stream'}
        </button>
        {isRunning && (
          <button
            onClick={stopStream}
            style={{ padding: '8px 16px', marginRight: '10px', backgroundColor: '#dc3545', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
          >
            Stop
          </button>
        )}
        <button
          onClick={clearEvents}
          style={{ padding: '8px 16px', backgroundColor: '#6c757d', color: 'white', border: 'none', borderRadius: '4px', cursor: 'pointer' }}
        >
          Clear Events
        </button>
      </div>

      <div style={{ marginBottom: '20px', fontSize: '14px', color: '#666' }}>
        Status: {isRunning ? 'Running' : 'Idle'} | Events: {events.length} | Graph: {graph ? 'Loaded' : 'None'}
        {events.length >= MAX_EVENTS && ` (Showing last ${MAX_EVENTS})`}
      </div>

      <div style={{ marginBottom: '20px' }}>
        <h4>Events ({events.length})</h4>
        <div style={{ backgroundColor: '#f8f9fa', border: '1px solid #dee2e6', borderRadius: '4px', maxHeight: '300px', overflow: 'auto' }}>
          <pre style={{ margin: '0', padding: '10px', fontSize: '12px' }}>
            {JSON.stringify(events.slice(-50), null, 2)}
          </pre>
        </div>
      </div>

      <div style={{ height: 400, border: '1px solid #dee2e6', borderRadius: '4px' }}>
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
        </ReactFlow>
      </div>
    </div>
  )
}
