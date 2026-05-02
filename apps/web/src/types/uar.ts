export type RuntimeEventType =
  | 'orchestration_plan'
  | 'start'
  | 'skill_start'
  | 'skill_complete'
  | 'skill_failed'
  | 'error'
  | 'complete'

export type RuntimeEvent = {
  schema_version: 'uar.event.v1'
  type: RuntimeEventType
  run_id: string
  goal_id: string
  skill: string | null
  timestamp: number
  payload: Record<string, unknown>
  error: string | null
}

export type OrchestrationGraphNode = {
  id: string
  skill: string
  depends_on: string[]
  metadata?: Record<string, unknown>
}

export type OrchestrationGraphEdge = {
  from: string
  to: string
}

export type OrchestrationGraph = {
  mode: string
  nodes: OrchestrationGraphNode[]
  edges: OrchestrationGraphEdge[]
}

export type NodeRunState = 'idle' | 'running' | 'complete' | 'failed'

export type RunRecord = {
  run_id: string
  goal_id: string
  skills: string[]
  outputs: Array<Record<string, unknown>>
  status: 'pending' | 'running' | 'completed' | 'failed'
  errors: string[]
  events: RuntimeEvent[]
  final_context: Record<string, unknown>
}
