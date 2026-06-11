import { authHeaders } from '../utils/auth'

async function fetchJson<T>(path: string, init?: RequestInit & { acceptStatus?: number[] }): Promise<T> {
  const url = `${window.location.origin}${path}`
  const headers = authHeaders(
    init?.body != null ? { 'Content-Type': 'application/json' } : {}
  )
  const response = await fetch(url, {
    ...init,
    headers: {
      ...headers,
      ...(init?.headers as Record<string, string> ?? {}),
    },
  })
  const isAccepted = init?.acceptStatus?.includes(response.status)
  if (!response.ok && !isAccepted) {
    const text = await response.text().catch(() => response.statusText)
    throw new Error(`HTTP ${response.status} ${response.statusText}: ${text}`)
  }
  return response.json() as Promise<T>
}

export interface HealthDashboardData {
  skills: { name: string; available: boolean; last_error?: string }[]
  circuit_breakers: { name: string; state: string }[]
  recent_errors: unknown[]
  server_version: string
  uptime_seconds: number
}

export interface RunRecord {
  run_id: string
  goal_id?: string
  status: string
  skills?: string[]
  timestamp?: number
  created_at?: number
  user_id?: string
}

export interface RunComparison {
  run_a: string
  run_b: string
  same_status: boolean
  same_skills: boolean
  diffs: Record<string, { a: unknown; b: unknown }>
}

export interface SkillPingResult {
  status: string
  skill: string
  latency_ms?: number
}

export interface CircuitBreakerInfo {
  state: string
  failures: number
  half_open_count: number
  half_open_successes: number
  last_failure_time: number
}

export interface CircuitBreakerStates {
  status: string
  circuits: Record<string, CircuitBreakerInfo>
}

export interface EvidencePackResponse {
  status: string
  run_id: string
  evidence_pack: Record<string, unknown>
  markdown: string | null
}

export interface TrustMovementRecord {
  recommendation_id: string
  run_id?: string | null
  before?: number | null
  after?: number | null
  delta?: number | null
  outcome_type?: string | null
  evidence_refs?: string[]
}

export interface TrustMovementResponse {
  status: string
  movements: TrustMovementRecord[]
}

export const dashboardApi = {
  healthDashboard(init?: RequestInit): Promise<HealthDashboardData> {
    return fetchJson('/api/health/dashboard', init)
  },

  listRuns(init?: RequestInit): Promise<RunRecord[]> {
    return fetchJson('/api/uar/runs', init)
  },

  compareRuns(a: string, b: string, init?: RequestInit): Promise<RunComparison> {
    return fetchJson(`/api/uar/runs/${encodeURIComponent(a)}/compare/${encodeURIComponent(b)}`, init)
  },

  evidencePack(runId: string, init?: RequestInit): Promise<EvidencePackResponse> {
    return fetchJson(
      `/api/uar/evidence-pack/${encodeURIComponent(runId)}?include_markdown=true`,
      init
    )
  },

  trustMovementPreview(body: {
    recommendation_ids: string[]
    run_id?: string | null
  }, init?: RequestInit): Promise<TrustMovementResponse> {
    return fetchJson('/api/uar/recommendations/trust-movement/preview', {
      method: 'POST',
      body: JSON.stringify(body),
      ...init,
    })
  },

  pingSkill(name: string, init?: RequestInit): Promise<SkillPingResult> {
    return fetchJson('/api/uar/skills/ping', {
      method: 'POST',
      body: JSON.stringify({ skill: name }),
      ...init,
    })
  },

  circuitBreakers(init?: RequestInit): Promise<CircuitBreakerStates> {
    return fetchJson('/api/health/circuit-breakers', {
      acceptStatus: [503],
      ...init,
    })
  },

  resetCircuitBreaker(name: string, init?: RequestInit): Promise<{ status: string }> {
    return fetchJson(`/api/health/circuit-breakers/${encodeURIComponent(name)}/reset`, {
      method: 'POST',
      ...init,
    })
  },

  bulkDeleteRuns(body: {
    run_ids?: string[]
    older_than_days?: number
  }, init?: RequestInit): Promise<{ deleted: number; filter: string }> {
    return fetchJson('/api/uar/runs/bulk-delete', {
      method: 'POST',
      body: JSON.stringify(body),
      ...init,
    })
  },
}
