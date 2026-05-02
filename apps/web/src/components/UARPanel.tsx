import { useMemo, useState } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'

const nodeTypes = {}
const edgeTypes = {}

type PlannerMode = 'simple' | 'llm'
type RunStatus = 'idle' | 'running' | 'completed' | 'failed'

const presets = [
  {
    label: 'Ask Ollama',
    description: 'Use the local Ollama model for a plain-language answer.',
    goal: 'Explain gravity simply',
    skills: ['ollama_generate']
  },
  {
    label: 'Stream Test',
    description: 'Validate the streaming event path.',
    goal: 'Stream test',
    skills: ['section_sum']
  },
  {
    label: 'Repo Map',
    description: 'Run document ingestion and dependency mapping on the repo.',
    goal: 'Map this repository',
    skills: ['doc_ingest', 'dependency_map', 'sum_review'],
    input_path: './'
  },
  {
    label: 'Demo Run',
    description: 'Run the simplest local runtime demonstration.',
    goal: 'Say hello from UAR',
    skills: ['section_sum']
  }
]

function downloadFile(filename: string, content: string, type: string) {
  const blob = new Blob([content], { type })
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  URL.revokeObjectURL(url)
}

function valueToText(value: unknown) {
  if (value === undefined || value === null) return ''
  if (typeof value === 'string') return value
  return JSON.stringify(value, null, 2)
}

function eventsToMarkdown(events: any[], graph: any, result: any) {
  const start = events.find((event) => event.type === 'start')
  const complete = [...events].reverse().find((event) => event.type === 'complete')
  const lines: string[] = []

  lines.push('# UAR Run')
  lines.push('')
  lines.push('## Goal')
  lines.push(start?.payload?.goal || 'No goal captured')
  lines.push('')
  lines.push('## Planner')
  lines.push(start?.payload?.planner || 'not captured')
  lines.push('')
  lines.push('## Skills')
  const capturedSkills = start?.payload?.skills || []
  if (capturedSkills.length) {
    capturedSkills.forEach((skill: string) => lines.push(`- ${skill}`))
  } else {
    lines.push('- No skills captured')
  }
  lines.push('')
  lines.push('## Status')
  lines.push(complete?.payload?.status || 'unknown')
  lines.push('')
  lines.push('## Result')
  lines.push('```')
  lines.push(valueToText(result || complete?.payload?.outputs || 'No result captured'))
  lines.push('```')
  lines.push('')
  lines.push('## Execution Plan')
  const graphNodes = graph?.nodes || []
  if (graphNodes.length) {
    graphNodes.forEach((node: any) => lines.push(`- ${node.skill || node.id}`))
  } else {
    lines.push('- No graph captured')
  }
  lines.push('')
  lines.push('## Events')
  events.forEach((event) => {
    lines.push(`- ${event.type}${event.skill ? `: ${event.skill}` : ''}${event.error ? ` — ${event.error}` : ''}`)
  })

  return `${lines.join('\n')}\n`
}

function eventsToStructure(events: any[], graph: any, result: any) {
  const start = events.find((event) => event.type === 'start')
  const complete = [...events].reverse().find((event) => event.type === 'complete')

  return {
    title: 'UAR Run',
    kind: 'run',
    children: [
      { title: 'Goal', kind: 'goal', value: start?.payload?.goal || '' },
      { title: 'Planner', kind: 'planner', value: start?.payload?.planner || 'not captured' },
      {
        title: 'Skills',
        kind: 'skills',
        children: (start?.payload?.skills || []).map((skill: string) => ({ title: skill, kind: 'skill' }))
      },
      { title: 'Status', kind: 'status', value: complete?.payload?.status || 'unknown' },
      { title: 'Result', kind: 'result', value: result || complete?.payload?.outputs || null },
      {
        title: 'Execution Plan',
        kind: 'plan',
        children: (graph?.nodes || []).map((node: any) => ({
          title: node.skill || node.id,
          kind: 'skill',
          value: { id: node.id, depends_on: node.depends_on || [] }
        }))
      },
      {
        title: 'Events',
        kind: 'events',
        children: events.map((event) => ({
          title: event.skill ? `${event.type}: ${event.skill}` : event.type,
          kind: 'event',
          value: { error: event.error, payload: event.payload }
        }))
      }
    ]
  }
}

function StructureTree({ node, depth = 0 }: { node: any; depth?: number }) {
  const [open, setOpen] = useState(depth < 2)
  const hasChildren = Boolean(node.children?.length)

  return (
    <div style={{ marginLeft: depth * 16, marginTop: 6 }}>
      <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
        {hasChildren && (
          <button onClick={() => setOpen((value) => !value)} style={{ padding: '0 6px' }}>
            {open ? '−' : '+'}
          </button>
        )}
        <strong>{node.title}</strong> <span style={{ color: '#777' }}>({node.kind})</span>
      </div>
      {node.value !== undefined && node.value !== null && node.value !== '' && (
        <pre style={{ whiteSpace: 'pre-wrap', margin: '4px 0 8px', color: '#333' }}>{valueToText(node.value)}</pre>
      )}
      {open && (node.children || []).map((child: any, index: number) => (
        <StructureTree key={`${child.title}-${index}`} node={child} depth={depth + 1} />
      ))}
    </div>
  )
}

export function UARPanel() {
  const [goal, setGoal] = useState('Explain gravity simply')
  const [skills, setSkills] = useState<string[]>(['ollama_generate'])
  const [inputPath, setInputPath] = useState<string | undefined>(undefined)
  const [plannerMode, setPlannerMode] = useState<PlannerMode>('simple')
  const [activePreset, setActivePreset] = useState('Ask Ollama')
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  const [result, setResult] = useState<any>(null)
  const [error, setError] = useState<string | null>(null)
  const [status, setStatus] = useState<RunStatus>('idle')
  const [showAdvanced, setShowAdvanced] = useState(false)

  const applyPreset = (preset: any) => {
    setGoal(preset.goal)
    setSkills(preset.skills)
    setInputPath(preset.input_path)
    setActivePreset(preset.label)
    setResult(null)
    setError(null)
    setEvents([])
    setGraph(null)
    setStatus('idle')
  }

  const runStream = async () => {
    setEvents([])
    setGraph(null)
    setResult(null)
    setError(null)
    setStatus('running')

    try {
      const body: Record<string, unknown> = { goal, skills, planner: plannerMode }
      if (inputPath) body.input_path = inputPath

      const res = await fetch('/api/v1/uar/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      })

      if (!res.ok) {
        throw new Error(`Request failed with HTTP ${res.status}`)
      }

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No response stream was returned')
      }

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })

        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          const lines = part.split('\n')
          for (const line of lines) {
            if (line.startsWith('data:')) {
              const json = JSON.parse(line.replace('data: ', ''))
              setEvents((prev) => [...prev, json])

              if (json.type === 'orchestration_plan' && json.payload?.graph) {
                setGraph(json.payload.graph)
              }

              if (json.type === 'skill_complete') {
                setResult(json.payload?.result)
              }

              if (json.type === 'complete') {
                setStatus(json.payload?.status === 'completed' ? 'completed' : 'failed')
                const outputs = json.payload?.outputs || []
                const lastOutput = outputs[outputs.length - 1]
                if (lastOutput) setResult(lastOutput)
                if (json.payload?.errors?.length) setError(json.payload.errors.join('\n'))
              }

              if (json.type === 'skill_failed') {
                setStatus('failed')
                setError(json.error || 'Skill failed')
                setResult({ error: json.error })
              }
            }
          }
        }
      }
    } catch (err) {
      setStatus('failed')
      setError(err instanceof Error ? err.message : 'Unknown error')
    }
  }

  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] }

    const nodeIndex = new Map<string, string>()

    const nodes = (graph.nodes || []).map((n: any, i: number) => {
      const nodeId = n.id || n.skill || String(i)
      nodeIndex.set(nodeId, String(i))
      return {
        id: String(i),
        data: { label: n.skill || String(nodeId).split('/').pop(), type: n.type || 'skill' },
        position: { x: (i % 5) * 180, y: Math.floor(i / 5) * 120 }
      }
    })

    const edges = (graph.edges || [])
      .map((e: any, i: number) => {
        const source = nodeIndex.get(e.from)
        const target = nodeIndex.get(e.to)
        if (!source || !target) return null
        return {
          id: String(i),
          source,
          target
        }
      })
      .filter(Boolean)

    return { nodes, edges }
  }, [graph])

  const resultText = useMemo(() => {
    if (error) return error
    if (!result) return 'Run a preset or enter a goal to see results here.'
    if (typeof result === 'string') return result
    if (result.response) return result.response
    return JSON.stringify(result, null, 2)
  }, [error, result])

  const markdownExport = useMemo(() => eventsToMarkdown(events, graph, result), [events, graph, result])
  const structureExport = useMemo(() => eventsToStructure(events, graph, result), [events, graph, result])

  const copyMarkdown = async () => {
    await navigator.clipboard.writeText(markdownExport)
  }

  return (
    <div style={{ fontFamily: 'system-ui, sans-serif', maxWidth: 1100, margin: '0 auto', padding: 20 }}>
      <header style={{ marginBottom: 20 }}>
        <h2 style={{ marginBottom: 4 }}>UAR Live System</h2>
        <p style={{ marginTop: 0, color: '#555' }}>Ask, run, inspect, and understand the runtime.</p>
      </header>

      <section style={{ display: 'grid', gap: 12, marginBottom: 20 }}>
        <label>
          <strong>Goal</strong>
          <textarea
            value={goal}
            onChange={(e) => setGoal(e.target.value)}
            placeholder="What do you want UAR to do?"
            rows={3}
            style={{ width: '100%', marginTop: 6 }}
          />
        </label>

        <div>
          <strong>Presets</strong>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: 8, marginTop: 8 }}>
            {presets.map((preset) => (
              <button
                key={preset.label}
                onClick={() => applyPreset(preset)}
                style={{ textAlign: 'left', padding: 10, border: activePreset === preset.label ? '2px solid #333' : '1px solid #ccc', borderRadius: 8 }}
              >
                <strong>{preset.label}</strong>
                <div style={{ color: '#666', fontSize: 12, marginTop: 4 }}>{preset.description}</div>
              </button>
            ))}
          </div>
        </div>

        <div>
          <strong>Planner Mode</strong>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
            <button
              onClick={() => setPlannerMode('simple')}
              style={{ padding: 10, border: plannerMode === 'simple' ? '2px solid #333' : '1px solid #ccc', borderRadius: 8 }}
            >
              Deterministic
            </button>
            <button
              onClick={() => setPlannerMode('llm')}
              style={{ padding: 10, border: plannerMode === 'llm' ? '2px solid #333' : '1px solid #ccc', borderRadius: 8 }}
            >
              Agent Mode
            </button>
            <span style={{ color: '#666', alignSelf: 'center' }}>
              {plannerMode === 'simple' ? 'Uses selected skills exactly.' : 'LLM may choose from registered skills only.'}
            </span>
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <button onClick={runStream} disabled={status === 'running'}>
            {status === 'running' ? 'Running...' : 'Run'}
          </button>
          <span>Status: <strong>{status}</strong></span>
          <span>Planner: <strong>{plannerMode}</strong></span>
          <span>Skills: {skills.join(' → ')}</span>
        </div>
      </section>

      {error && (
        <section style={{ border: '1px solid #d66', background: '#fff4f4', borderRadius: 8, padding: 16, marginBottom: 20 }}>
          <h3 style={{ marginTop: 0 }}>Something needs attention</h3>
          <pre style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{error}</pre>
        </section>
      )}

      <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Result</h3>
        <pre style={{ whiteSpace: 'pre-wrap', marginBottom: 0 }}>{resultText}</pre>
      </section>

      <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Structure</h3>
        <StructureTree node={structureExport} />
        <div style={{ display: 'flex', gap: 8, marginTop: 12, flexWrap: 'wrap' }}>
          <button onClick={copyMarkdown} disabled={!events.length}>Copy Markdown</button>
          <button onClick={() => downloadFile('uar-run.md', markdownExport, 'text/markdown')} disabled={!events.length}>Download Markdown</button>
          <button onClick={() => downloadFile('uar-run.structure.json', JSON.stringify(structureExport, null, 2), 'application/json')} disabled={!events.length}>Download Structure JSON</button>
        </div>
      </section>

      <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16, marginBottom: 20 }}>
        <h3 style={{ marginTop: 0 }}>Execution Map</h3>
        <div style={{ height: 400 }}>
          <ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} edgeTypes={edgeTypes} fitView>
            <Background />
          </ReactFlow>
        </div>
      </section>

      <section style={{ border: '1px solid #ddd', borderRadius: 8, padding: 16 }}>
        <button onClick={() => setShowAdvanced((value) => !value)}>
          {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
        </button>
        {showAdvanced && (
          <div style={{ marginTop: 12 }}>
            <h3>Events</h3>
            <pre style={{ whiteSpace: 'pre-wrap' }}>{JSON.stringify(events, null, 2)}</pre>
          </div>
        )}
      </section>
    </div>
  )
}
