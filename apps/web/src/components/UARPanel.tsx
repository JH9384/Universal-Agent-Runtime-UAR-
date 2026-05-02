import { useState } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'

export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)

  const runStream = async () => {
    const res = await fetch('/api/uar/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, skills: ['doc_ingest','dependency_map','sum_review'], input_path: './' })
    })

    const reader = res.body?.getReader()
    const decoder = new TextDecoder()

    if (!reader) return

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

            if (json.run?.final_context?.dependency_map) {
              setGraph(json.run.final_context.dependency_map)
            }
          }
        }
      }
    }
  }

  const buildFlow = () => {
    if (!graph) return { nodes: [], edges: [] }

    const nodeIndex = new Map()

    const nodes = graph.nodes.map((n, i) => {
      nodeIndex.set(n.id, String(i))
      return {
        id: String(i),
        data: { label: n.id.split('/').pop(), type: n.type },
        position: { x: (i % 5) * 150, y: Math.floor(i / 5) * 100 }
      }
    })

    const edges = graph.edges
      .map((e, i) => {
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
  }

  const { nodes, edges } = buildFlow()

  return (
    <div>
      <h3>UAR Live System</h3>
      <input value={goal} onChange={(e) => setGoal(e.target.value)} />
      <button onClick={runStream}>Run Stream</button>

      <div>
        <h4>Events</h4>
        <pre>{JSON.stringify(events, null, 2)}</pre>
      </div>

      <div style={{ height: 400 }}>
        <ReactFlow nodes={nodes} edges={edges}>
          <Background />
        </ReactFlow>
      </div>
    </div>
  )
}
