import { useState } from 'react'

export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)

  const runStream = () => {
    const evtSource = new EventSource('/api/uar/stream')

    evtSource.onmessage = (e) => {
      const data = JSON.parse(e.data)
      setEvents((prev) => [...prev, data])

      if (data.run?.final_context?.dependency_map) {
        setGraph(data.run.final_context.dependency_map)
      }
    }
  }

  const renderGraph = () => {
    if (!graph) return null

    const nodes = graph.nodes.slice(0, 10)
    const edges = graph.edges.slice(0, 10)

    return (
      <svg width={400} height={300} style={{ border: '1px solid gray' }}>
        {nodes.map((n, i) => (
          <circle key={i} cx={50 + i * 30} cy={150} r={10} fill="blue" />
        ))}
        {edges.map((e, i) => (
          <line key={i} x1={50} y1={150} x2={80 + i * 30} y2={150} stroke="black" />
        ))}
      </svg>
    )
  }

  return (
    <div>
      <h3>UAR Streaming Panel</h3>
      <input value={goal} onChange={(e) => setGoal(e.target.value)} />
      <button onClick={runStream}>Run Stream</button>

      <div>
        <h4>Events</h4>
        <pre>{JSON.stringify(events, null, 2)}</pre>
      </div>

      <div>
        <h4>Graph</h4>
        {renderGraph()}
      </div>
    </div>
  )
}
