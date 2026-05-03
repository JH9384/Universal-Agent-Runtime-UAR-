import { useMemo, useState, useCallback } from 'react'
import ReactFlow, { Background } from 'reactflow'
import 'reactflow/dist/style.css'
import 'reactflow/dist/style.css'
import '../design-system/tokens.css'
import '../design-system/components.css'
import { getApiUrl } from '../config'

// Types for better TypeScript support
interface UAREvent {
  type: string
  payload?: any
  run?: any
  timestamp?: number
}

interface GraphData {
  nodes: Array<{
    id?: string
    skill?: string
    type?: string
  }>
  edges: Array<{
    from: string
    to: string
  }>
}

type LoadingState = 'idle' | 'loading' | 'success' | 'error'

interface FormErrors {
  goal?: string
}

export function UARPanelImproved() {
  const [goal, setGoal] = useState('')
  const [events, setEvents] = useState<UAREvent[]>([])
  const [graph, setGraph] = useState<GraphData | null>(null)
  const [loadingState, setLoadingState] = useState<LoadingState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [formErrors, setFormErrors] = useState<FormErrors>({})
  
  // Limit events to prevent memory leaks
  const MAX_EVENTS = 1000

  // Validate form
  const validateForm = useCallback((): boolean => {
    const errors: FormErrors = {}
    
    if (!goal.trim()) {
      errors.goal = 'Please enter a goal to proceed'
    } else if (goal.trim().length < 3) {
      errors.goal = 'Goal must be at least 3 characters long'
    } else if (goal.trim().length > 500) {
      errors.goal = 'Goal must be less than 500 characters'
    }
    
    setFormErrors(errors)
    return Object.keys(errors).length === 0
  }, [goal])

  // Handle form submission
  const handleSubmit = useCallback(async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!validateForm()) {
      return
    }
    
    setLoadingState('loading')
    setError(null)
    setEvents([])
    setGraph(null)

    try {
      const res = await fetch(getApiUrl('/api/uar/stream'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          goal: goal.trim(), 
          skills: ['doc_ingest', 'dependency_map', 'sum_review'], 
          input_path: './' 
        })
      })

      if (!res.ok) {
        throw new Error(`HTTP ${res.status}: ${res.statusText}`)
      }

      const reader = res.body?.getReader()
      const decoder = new TextDecoder()

      if (!reader) {
        throw new Error('No response body available')
      }

      let buffer = ''
      let eventCount = 0

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
                const json = JSON.parse(line.replace('data: ', '')) as UAREvent
                json.timestamp = Date.now()
                
                setEvents((prev) => {
                  const newEvents = [...prev, json]
                  // Keep only the last MAX_EVENTS events
                  return newEvents.length > MAX_EVENTS 
                    ? newEvents.slice(-MAX_EVENTS) 
                    : newEvents
                })

                eventCount++

                // Update graph when orchestration plan or dependency map is received
                if (json.type === 'orchestration_plan' && json.payload?.graph) {
                  setGraph(json.payload.graph)
                }

                if (json.run?.final_context?.dependency_map) {
                  setGraph(json.run.final_context.dependency_map)
                }
              } catch (parseError) {
                console.error('Failed to parse streaming data:', parseError, 'Line:', line)
                // Continue processing other events
              }
            }
          }
        }
      }

      setLoadingState('success')
      
      // Show success message temporarily
      setTimeout(() => {
        if (eventCount > 0) {
          setLoadingState('idle')
        }
      }, 3000)

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'An unknown error occurred'
      setError(errorMessage)
      setLoadingState('error')
      
      // Clear error after 10 seconds
      setTimeout(() => {
        setError(null)
        setLoadingState('idle')
      }, 10000)
    }
  }, [goal, validateForm])

  // Handle input changes
  const handleGoalChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    setGoal(e.target.value)
    // Clear form error when user starts typing
    if (formErrors.goal) {
      setFormErrors(prev => ({ ...prev, goal: undefined }))
    }
  }, [formErrors.goal])

  // Handle retry
  const handleRetry = useCallback(() => {
    setError(null)
    setLoadingState('idle')
    handleSubmit(new Event('submit') as any)
  }, [handleSubmit])

  // Process graph data for ReactFlow
  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] }

    const nodeIndex = new Map<string, string>()

    const processedNodes = (graph.nodes || []).map((n, i) => {
      const nodeId = n.id || n.skill || String(i)
      nodeIndex.set(nodeId, String(i))
      return {
        id: String(i),
        data: { 
          label: n.skill || String(nodeId).split('/').pop(), 
          type: n.type || 'skill' 
        },
        position: { 
          x: (i % 5) * 180, 
          y: Math.floor(i / 5) * 120 
        },
        className: n.type === 'output' ? 'uar-reactflow-node uar-reactflow-node-output' : 'uar-reactflow-node'
      }
    })

    const processedEdges = (graph.edges || [])
      .map((e, i) => {
        const source = nodeIndex.get(e.from)
        const target = nodeIndex.get(e.to)
        if (!source || !target) return null
        return {
          id: String(i),
          source,
          target,
          className: 'uar-reactflow-edge'
        }
      })
      .filter((edge): edge is NonNullable<typeof edge> => edge !== null)

    return { nodes: processedNodes, edges: processedEdges }
  }, [graph])

  // Format events for display
  const formattedEvents = useMemo(() => {
    return events.slice(-20).reverse() // Show last 20 events, newest first
  }, [events])

  return (
    <div className="uar-layout">
      <header className="uar-header">
        <h1 className="uar-heading-1">UAR Control Surface</h1>
        <p className="uar-text-secondary">
          Universal Agent Runtime - Execute complex tasks with AI-powered orchestration
        </p>
      </header>

      <main className="uar-main">
        {/* Goal Input Section */}
        <section className="uar-section">
          <div className="uar-card">
            <div className="uar-card-header">
              <h2 className="uar-card-title">Task Configuration</h2>
              <p className="uar-card-description">
                Define your goal and let UAR orchestrate the execution across multiple AI skills
              </p>
            </div>

            <form onSubmit={handleSubmit} className="uar-form">
              <div className="uar-form-row">
                <div className="uar-form-flex">
                  <label htmlFor="goal-input" className="uar-sr-only">
                    Enter your goal
                  </label>
                  <input
                    id="goal-input"
                    type="text"
                    value={goal}
                    onChange={handleGoalChange}
                    placeholder="Enter a goal (e.g., 'Analyze this codebase and generate documentation')"
                    className={`uar-input ${formErrors.goal ? 'uar-input-error' : ''}`}
                    disabled={loadingState === 'loading'}
                    aria-describedby={formErrors.goal ? 'goal-error' : undefined}
                    maxLength={500}
                  />
                  {formErrors.goal && (
                    <div id="goal-error" className="uar-alert uar-alert-error" role="alert">
                      {formErrors.goal}
                    </div>
                  )}
                </div>
                
                <button
                  type="submit"
                  disabled={loadingState === 'loading'}
                  className="uar-button"
                  aria-describedby={loadingState === 'loading' ? 'loading-status' : undefined}
                >
                  {loadingState === 'loading' ? (
                    <>
                      <div className="uar-spinner" aria-hidden="true" />
                      Processing...
                    </>
                  ) : (
                    'Execute Task'
                  )}
                </button>
              </div>

              {loadingState === 'loading' && (
                <div id="loading-status" className="uar-status uar-status-loading" role="status" aria-live="polite">
                  <div className="uar-spinner" aria-hidden="true" />
                  Executing task with AI skills...
                </div>
              )}
            </form>
          </div>
        </section>

        {/* Error Display */}
        {error && (
          <section className="uar-section" aria-live="assertive">
            <div className="uar-alert uar-alert-error" role="alert">
              <strong>Error:</strong> {error}
              <button 
                onClick={handleRetry}
                className="uar-button uar-button-secondary uar-button-retry"
              >
                Retry
              </button>
            </div>
          </section>
        )}

{/* Success Display */}
        {loadingState === 'success' && (
          <section className="uar-section" aria-live="polite">
            <div className="uar-alert uar-alert-success" role="status">
              <strong>Success!</strong> Task completed with {events.length} events processed.
            </div>
          </section>
        )}

        {/* Results Section */}
        {(events.length > 0 || graph) && (
          <section className="uar-section">
            <div className="uar-card">
              <div className="uar-card-header">
                <h2 className="uar-card-title">Execution Results</h2>
                <div className="uar-status uar-status-success">
                  {events.length} events processed
                </div>
              </div>

              {/* Graph Visualization */}
              {graph && (
                <div className="uar-section">
                  <h3 className="uar-heading-3">Dependency Graph</h3>
                  <div className="uar-graph-container">
                    <ReactFlow nodes={nodes} edges={edges} fitView>
                      <Background />
                    </ReactFlow>
                  </div>
                </div>
              )}

              {/* Event List */}
              {events.length > 0 && (
                <div className="uar-section">
                  <h3 className="uar-heading-3">Event Log</h3>
                  <div className="uar-event-list">
                    {formattedEvents.map((event, index) => (
                      <div key={index} className="uar-event-item">
                        <div className="uar-event-type">
                          {event.type}
                        </div>
                        <div className="uar-event-timestamp">
                          {event.timestamp && new Date(event.timestamp).toLocaleTimeString()}
                        </div>
                        <pre className="uar-event-content">
                          {JSON.stringify(event.payload || event.run, null, 2)}
                        </pre>
                      </div>
                    ))}
                    {events.length > 20 && (
                      <div className="uar-event-item uar-event-more">
                        ... and {events.length - 20} more events
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          </section>
        )}

        {/* Help Section */}
        {events.length === 0 && loadingState === 'idle' && (
          <section className="uar-section">
            <div className="uar-card uar-help-text">
              <h3 className="uar-heading-3">Getting Started</h3>
              <p className="uar-text">
                Enter a goal above and click "Execute Task" to begin. UAR will orchestrate multiple AI skills to accomplish your objective.
              </p>
              <div className="uar-button-group">
                <div className="uar-status uar-status-info">
                  doc_ingest
                </div>
                <div className="uar-status uar-status-info">
                  dependency_map
                </div>
                <div className="uar-status uar-status-info">
                  sum_review
                </div>
              </div>
            </div>
          </section>
        )}
      </main>
    </div>
  )
}
