import { useMemo, useState } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'
import { getApiUrl } from '../config'

export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  
  // Limit events to prevent memory leaks
  const MAX_EVENTS = 1000

  const runStream = async () => {
    setEvents([])
    setGraph(null)

    const res = await fetch(getApiUrl('/api/uar/stream'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, skills: ['doc_ingest', 'dependency_map', 'sum_review'], input_path: './' })
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
            try {
              const json = JSON.parse(line.replace('data: ', ''))
              setEvents((prev) => {
                const newEvents = [...prev, json]
                // Keep only the last MAX_EVENTS events
                return newEvents.length > MAX_EVENTS 
                  ? newEvents.slice(-MAX_EVENTS) 
                  : newEvents
              })

            if (json.type === 'orchestration_plan' && json.payload?.graph) {
              setGraph(json.payload.graph)
            }

            if (json.run?.final_context?.dependency_map) {
              setGraph(json.run.final_context.dependency_map)
            }
            } catch (error) {
              console.error('Failed to parse streaming data:', error, 'Line:', line)
            }
          }
        }
      }
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

  return (
    <div>
      <h3>UAR Live System</h3>
      <input value={goal} onChange={(e) => setGoal(e.target.value)} placeholder="Enter a goal" />
      <button onClick={runStream}>Run Stream</button>

      <div>
        <h4>Events</h4>
        <pre>{JSON.stringify(events, null, 2)}</pre>
      </div>

      <div style={{ height: 400 }}>
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
        </ReactFlow>
      </div>
    </div>
  )
}
