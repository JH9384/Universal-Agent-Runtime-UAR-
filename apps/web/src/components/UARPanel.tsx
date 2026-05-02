import { useMemo, useState } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'

const nodeTypes = {}
const edgeTypes = {}

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

export function UARPanel() {
  const [goal, setGoal] = useState('Explain gravity simply')
  const [skills, setSkills] = useState<string[]>(['ollama_generate'])
  const [plannerMode, setPlannerMode] = useState<'simple' | 'llm'>('simple')
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  const [result, setResult] = useState<any>(null)
  const [status, setStatus] = useState<'idle' | 'running' | 'completed' | 'failed'>('idle')

  const runStream = async () => {
    setStatus('running')

    const res = await fetch('/api/v1/uar/stream', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ goal, skills, planner: plannerMode })
    })

    const reader = res.body?.getReader()
    const decoder = new TextDecoder()

    let buffer = ''

    while (true) {
      const { done, value } = await reader!.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })

      const parts = buffer.split('\n\n')
      buffer = parts.pop() || ''

      for (const part of parts) {
        const line = part.split('\n').find(l => l.startsWith('data:'))
        if (!line) continue

        const json = JSON.parse(line.replace('data: ', ''))
        setEvents(prev => [...prev, json])

        if (json.type === 'orchestration_plan') setGraph(json.payload.graph)
        if (json.type === 'complete') setStatus('completed')
      }
    }
  }

  return (
    <div style={{ padding: 20 }}>
      <h2>UAR</h2>

      <textarea value={goal} onChange={e => setGoal(e.target.value)} />

      <div>
        <button onClick={() => setPlannerMode('simple')}>Deterministic</button>
        <button onClick={() => setPlannerMode('llm')}>Agent Mode</button>
      </div>

      <button onClick={runStream}>Run</button>

      <div>Status: {status}</div>

      <div style={{ height: 300 }}>
        <ReactFlow nodes={(graph?.nodes || []).map((n:any,i:number)=>({id:String(i),data:{label:n.skill},position:{x:i*100,y:0}}))} edges={[]} fitView>
          <Background />
        </ReactFlow>
      </div>
    </div>
  )
}
