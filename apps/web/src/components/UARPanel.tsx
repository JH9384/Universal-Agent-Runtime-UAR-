import { useMemo, useState, useRef, useCallback, useEffect } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'

const MAX_EVENTS = 1000 // Limit events to prevent memory leaks

export function UARPanel() {
  const [goal, setGoal] = useState('')
  const [events, setEvents] = useState<any[]>([])
  const [graph, setGraph] = useState<any>(null)
  const [isRunning, setIsRunning] = useState(false)
  const [error, setError] = useState<string | null>(null)
  
  const abortControllerRef = useRef<AbortController | null>(null)
  const eventCountRef = useRef(0)

  // Cleanup function
  const cleanup = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    setIsRunning(false)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return cleanup
  }, [cleanup])

  const runStream = useCallback(async () => {
    // Reset state
    setEvents([])
    setGraph(null)
    setError(null)
    setIsRunning(true)
    eventCountRef.current = 0

    // Create new abort controller
    abortControllerRef.current = new AbortController()

    try {
      const res = await fetch('/api/uar/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          goal, 
          skills: ['doc_ingest', 'dependency_map', 'sum_review'], 
          input_path: './' 
        }),
        signal: abortControllerRef.current.signal
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No response body reader available')
      }

      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        // Check if aborted
        if (abortControllerRef.current?.signal.aborted) {
          break
        }

        buffer += decoder.decode(value, { stream: true })

        const parts = buffer.split('\n\n')
        buffer = parts.pop() || ''

        for (const part of parts) {
          const lines = part.split('\n')
          for (const line of lines) {
            if (line.startsWith('data:')) {
              try {
                const json = JSON.parse(line.replace('data: ', ''))
                
                // Limit events to prevent memory leaks
                eventCountRef.current++
                if (eventCountRef.current > MAX_EVENTS) {
                  setEvents((prev) => {
                    const newEvents = [...prev, json]
                    return newEvents.slice(-MAX_EVENTS) // Keep only the latest MAX_EVENTS
                  })
                } else {
                  setEvents((prev) => [...prev, json])
                }

                if (json.type === 'orchestration_plan' && json.payload?.graph) {
                  setGraph(json.payload.graph)
                }

                if (json.run?.final_context?.dependency_map) {
                  setGraph(json.run.final_context.dependency_map)
                }

                // Handle error events
                if (json.type === 'error' && json.error) {
                  setError(json.error)
                }

              } catch (parseError) {
                console.error('Failed to parse SSE data:', parseError, 'Data:', line)
                setError('Failed to parse server response')
              }
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
  }, [goal])

  const stopStream = useCallback(() => {
    cleanup()
  }, [cleanup])

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

  const clearEvents = useCallback(() => {
    setEvents([])
    setError(null)
  }, [])

  return (
    <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
      <h3>UAR Live System</h3>
      
      {/* Error Display */}
      {error && (
        <div style={{ 
          backgroundColor: '#fee', 
          border: '1px solid #fcc', 
          padding: '10px', 
          marginBottom: '20px',
          borderRadius: '4px'
        }}>
          <strong>Error:</strong> {error}
          <button 
            onClick={() => setError(null)} 
            style={{ marginLeft: '10px', padding: '2px 8px' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Controls */}
      <div style={{ marginBottom: '20px' }}>
        <input 
          value={goal} 
          onChange={(e: any) => setGoal(e.target.value)} 
          placeholder="Enter a goal" 
          disabled={isRunning}
          style={{ 
            padding: '8px', 
            marginRight: '10px', 
            width: '300px',
            border: '1px solid #ccc',
            borderRadius: '4px'
          }} 
        />
        <button 
          onClick={runStream} 
          disabled={isRunning || !goal.trim()}
          style={{ 
            padding: '8px 16px', 
            marginRight: '10px',
            backgroundColor: isRunning ? '#ccc' : '#007bff',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: isRunning ? 'not-allowed' : 'pointer'
          }}
        >
          {isRunning ? 'Running...' : 'Run Stream'}
        </button>
        {isRunning && (
          <button 
            onClick={stopStream}
            style={{ 
              padding: '8px 16px', 
              marginRight: '10px',
              backgroundColor: '#dc3545',
              color: 'white',
              border: 'none',
              borderRadius: '4px',
              cursor: 'pointer'
            }}
          >
            Stop
          </button>
        )}
        <button 
          onClick={clearEvents}
          style={{ 
            padding: '8px 16px',
            backgroundColor: '#6c757d',
            color: 'white',
            border: 'none',
            borderRadius: '4px',
            cursor: 'pointer'
          }}
        >
          Clear Events
        </button>
      </div>

      {/* Status */}
      <div style={{ marginBottom: '20px', fontSize: '14px', color: '#666' }}>
        Status: {isRunning ? 'Running' : 'Idle'} | 
        Events: {events.length} | 
        Graph: {graph ? 'Loaded' : 'None'}
        {events.length >= MAX_EVENTS && ` (Showing last ${MAX_EVENTS})`}
      </div>

      {/* Events Display */}
      <div style={{ marginBottom: '20px' }}>
        <h4>Events ({events.length})</h4>
        <div style={{ 
          backgroundColor: '#f8f9fa', 
          border: '1px solid #dee2e6', 
          borderRadius: '4px',
          maxHeight: '300px',
          overflow: 'auto'
        }}>
          <pre style={{ margin: '0', padding: '10px', fontSize: '12px' }}>
            {JSON.stringify(events.slice(-50), null, 2)}
          </pre>
        </div>
      </div>

      {/* Graph Display */}
      <div style={{ height: 400, border: '1px solid #dee2e6', borderRadius: '4px' }}>
        <ReactFlow nodes={nodes} edges={edges} fitView>
          <Background />
        </ReactFlow>
      </div>
    </div>
  )
}
