declare global {
  interface Window {
    UAR_API_URL?: string;
  }
}

const DEFAULT_BASE_URL =
  typeof window !== "undefined"
    ? window.location.origin
    : "http://localhost:8000";

function getBaseUrl(): string {
  if (typeof window !== "undefined" && window.UAR_API_URL) {
    return window.UAR_API_URL;
  }
  return DEFAULT_BASE_URL;
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const url = `${getBaseUrl()}${path}`;
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(
      `HTTP ${response.status} ${response.statusText}: ${text}`
    );
  }
  return response.json() as Promise<T>;
}

export interface HealthDashboardData {
  skills: { name: string; available: boolean; last_error?: string }[];
  circuit_breakers: { name: string; state: string }[];
  recent_errors: unknown[];
  server_version: string;
  uptime_seconds: number;
}

export interface RunRecord {
  run_id: string;
  goal_id?: string;
  status: string;
  skills?: string[];
  timestamp?: string;
  user_id?: string;
}

export interface RunComparison {
  run_a: string;
  run_b: string;
  same_status: boolean;
  same_skills: boolean;
  diffs: Record<string, { a: unknown; b: unknown }>;
}

export interface SkillPingResult {
  status: string;
  skill: string;
  latency_ms?: number;
}

export interface CircuitBreakerStates {
  status: string;
  circuits: Record<string, { state: string; failures: number }>;
}

export const api = {
  healthDashboard(): Promise<HealthDashboardData> {
    return fetchJson("/api/health/dashboard");
  },

  listRuns(): Promise<RunRecord[]> {
    return fetchJson("/api/uar/runs");
  },

  compareRuns(a: string, b: string): Promise<RunComparison> {
    return fetchJson(`/api/uar/runs/${a}/compare/${b}`);
  },

  pingSkill(name: string): Promise<SkillPingResult> {
    return fetchJson("/api/uar/skills/ping", {
      method: "POST",
      body: JSON.stringify({ skill: name }),
    });
  },

  circuitBreakers(): Promise<CircuitBreakerStates> {
    return fetchJson("/api/health/circuit-breakers");
  },

  resetCircuitBreaker(name: string): Promise<{ status: string }> {
    return fetchJson(`/api/health/circuit-breakers/${name}/reset`, {
      method: "POST",
    });
  },

  bulkDeleteRuns(body: {
    run_ids?: string[];
    older_than_days?: number;
  }): Promise<{ deleted: number; filter: string }> {
    return fetchJson("/api/uar/runs/bulk-delete", {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
};
