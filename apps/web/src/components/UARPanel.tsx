import { useState } from 'react'

export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [output, setOutput] = useState<any>(null)

  const runGoal = async () => {
    const res = await fetch('/api/uar/run', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, skills: ['doc_ingest','dependency_map','sum_review'], input_path: './' })
    })

    const data = await res.json()
    setOutput(data)
  }

  const graph = output?.final_context?.dependency_map

  return (
    <div style={{ padding: 12, border: '1px solid #333' }}>
      <h3>UAR Control Panel</h3>
      <input
        value={goal}
        onChange={(e) => setGoal(e.target.value)}
        placeholder="Enter goal"
      />
      <button onClick={runGoal}>Run</button>

      <pre>{JSON.stringify(output, null, 2)}</pre>

      {graph && (
        <div>
          <h4>Graph</h4>
          <div>Nodes: {graph.node_count}</div>
          <div>Edges: {graph.edge_count}</div>
        </div>
      )}
    </div>
  )
}
