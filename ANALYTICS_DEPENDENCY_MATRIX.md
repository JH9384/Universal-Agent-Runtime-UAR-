# Analytics Dependency Matrix

## UAR Analytics Review — Audit A
**Scope:** Frontend components, backend endpoints, source data, derived metrics  
**Date:** 2026-06-01  
**Commit Base:** 57ed78b  
**Status:** Complete

---

## Legend

| Symbol | Meaning |
|--------|---------|
| `RunRecord` | SQLite/Postgres run record (events, skills, status, metadata, timestamps) |
| `MCHist` | In-memory `_MC_HISTORY` ring buffer (up to 100 snapshots) |
| `BurnHist` | In-memory `_BURNIN_HISTORY` ring buffer |
| `Store.*` | Direct store query (`list_records`, `get_by_run_id`) |
| `Health` | Runtime health endpoint (`/api/health/dashboard`) |
| `Registry` | Skill/recipe registry (static configuration) |

---

## Matrix

### 1. Mission Control (Primary Dashboard)

| Field | Value |
|-------|-------|
| **Component** | `MissionControlWidget.tsx` |
| **Endpoints** | `GET /api/uar/mission-control` (30s poll)  
`GET /api/health/dashboard` (30s poll) |
| **Source Data** | `MCHist` + `Store.latest` + `BurnHist` + `Registry` + `Health` |
| **Derived Metrics** | Runtime Health score+tier, Replay Confidence score+tier, Certification score+level, Active Runs count, Skill Availability ratio, Circuit Breaker state, Burn-In evidence, Recent Warnings |
| **Sub-components Embedded** | `ConfidenceDriftPanel`, `TrendPanel`, `BurnInHistory`, `FailureClusterPanel`, `TopologyWidget`, `TopologyAnalyticsPanel`, `FailureHotspotPanel`, `RecipeIntelligencePanel` |
| **Storage Layer** | Zero new storage. MC snapshot assembled on-demand from existing stores. `_MC_HISTORY` is in-memory only. |
| **Poll Interval** | 30s (both endpoints) |

---

### 2. Trends

| Field | Value |
|-------|-------|
| **Component** | `TrendPanel.tsx` |
| **Endpoint** | `GET /api/uar/mission-control/history?hours=24` |
| **Source Data** | `MCHist` (in-memory snapshot ring buffer) |
| **Derived Metrics** | Health score sparkline, Confidence score sparkline, Certification score sparkline (min/max/current) |
| **Depends On** | Mission Control being queried (MC history is only populated when `/api/uar/mission-control` is called) |
| **Key Risk** | If MC endpoint is never polled, trends show empty state. No explicit backfill. |

---

### 3. Burn-In History

| Field | Value |
|-------|-------|
| **Component** | `BurnInHistory.tsx` |
| **Endpoint** | `GET /api/uar/burnin/history?limit=20` |
| **Source Data** | `BurnHist` (in-memory) |
| **Derived Metrics** | Pass rate, average score, score sparkline, per-report score + pass/fail state |
| **Storage Layer** | In-memory only. Resets on restart. `BurnInProxy.snapshot_latest()` falls back to store on cache miss. |

---

### 4. Replay Explorer

| Field | Value |
|-------|-------|
| **Component** | `ReplayExplorer.tsx` |
| **Endpoint** | `GET /api/uar/runs/{run_id}/explorer` |
| **Source Data** | `Store.get_by_run_id(run_id)` |
| **Derived Metrics** | Summary (status, skills, goal, created_at), Timeline (event sequence), Confidence (`score_replay`), Failure Path (error events), Raw Events |
| **Trigger** | Operator clicks "Explore" from Runs History panel |
| **Storage Layer** | Direct record read. No aggregation. |

---

### 5. Compare Runs

| Field | Value |
|-------|-------|
| **Component** | `CompareRuns.tsx` |
| **Endpoint** | `GET /api/uar/runs/{run_a}/compare/{run_b}` |
| **Source Data** | `Store.get_by_run_id` for both runs |
| **Derived Metrics** | Confidence delta, Event count delta, Failure count delta, Skill added/removed sets, Failed skill lists, Verdict (improved/degraded/mixed/equivalent) |
| **Trigger** | Operator clicks "Compare" from Runs History panel |
| **Storage Layer** | Direct record reads. No aggregation index. |

---

### 6. Failure Clusters

| Field | Value |
|-------|-------|
| **Component** | `FailureClusterPanel.tsx` |
| **Endpoint** | `GET /api/uar/runs/failure-clusters?hours=24&top=10` |
| **Source Data** | `Store.list_records` → filter by `created_at/timestamp >= cutoff` |
| **Derived Metrics** | Top failing skills (count, run_count, latest_error), Top error patterns (count, run_count, skill_count), Total failures, Total runs scanned |
| **Aggregation** | O(N*E) full table scan over all runs + all events per run. No index on `created_at` or event fields. |

---

### 7. Confidence Drift

| Field | Value |
|-------|-------|
| **Component** | `ConfidenceDriftPanel.tsx` |
| **Endpoint** | `GET /api/uar/confidence-drift?hours=24` |
| **Source Data** | `MCHist` (confidence scores) + `Store.list_records` (recent runs, events) + `BurnHist` (burn-in scores) |
| **Derived Metrics** | Previous score, Current score, Delta, State (stable/improving/degrading), Confidence history sparkline, Top contributors (failures, errors, burn-in drops), Failure summary |
| **Key Logic** | Delta > 5 → improving; Delta < -5 → degrading. Contributors only populated when state != stable. |
| **Depends On** | MC history (for confidence trend) AND store scan (for failure contributors) |

---

### 8. Topology (Registry View)

| Field | Value |
|-------|-------|
| **Component** | `TopologyWidget.tsx` |
| **Endpoints** | `GET /api/uar/skills`  
`GET /api/uar/recipes`  
`GET /api/health/dashboard` |
| **Source Data** | `Registry` (static skill/recipe definitions) + `Health` (availability) |
| **Derived Metrics** | Skill category grouping, Recipe → skill edge matrix, Skill availability overlay |
| **Storage Layer** | No execution data. Pure registry view. |

---

### 9. Topology Analytics (Execution View)

| Field | Value |
|-------|-------|
| **Component** | `TopologyAnalyticsPanel.tsx` |
| **Endpoint** | `GET /api/uar/topology/hot-paths?hours=168&top=10` |
| **Source Data** | `Store.list_records` → filter by `created_at/timestamp >= cutoff` |
| **Derived Metrics** | Hot nodes (skill invocations, success rate), Hot edges (skill→skill transitions, success rate), Recipe utilization (executions, success rate) |
| **Aggregation** | O(N*S) full table scan. Builds node/edge/recipe dicts from `skills` list and `metadata.execution_order`. |

---

### 10. Failure Hotspots

| Field | Value |
|-------|-------|
| **Component** | `FailureHotspotPanel.tsx` |
| **Endpoint** | `GET /api/uar/topology/failure-hotspots?hours=168&top=10` |
| **Source Data** | `Store.list_records` → filter by `created_at/timestamp >= cutoff` |
| **Derived Metrics** | Node failure rate + severity (critical/warning/healthy), Edge failure rate + severity, Affected run counts |
| **Aggregation** | O(N*E) full table scan. Same source data as `FailureClusterPanel` but grouped by topology instead of error message. |

---

### 11. Recipe Intelligence

| Field | Value |
|-------|-------|
| **Component** | `RecipeIntelligencePanel.tsx` |
| **Endpoint** | `GET /api/uar/recipes/intelligence?hours=168` |
| **Source Data** | `Store.list_records` → filter by `created_at/timestamp >= cutoff` |
| **Derived Metrics** | Per-recipe: executions, success_rate, failure_rate, avg_confidence, avg_duration_ms, classification (recommended/monitor/retire) |
| **Classification Rules** | `success_rate >= 0.9 && executions >= 3` → recommended  
`failure_rate >= 0.5 \|\| (success_rate < 0.5 && executions >= 3)` → retire  
otherwise → monitor |
| **Aggregation** | O(N*R) full table scan over `metadata.execution_order` to count recipe instances. |

---

## Cross-Reference: Metrics by Source

### Metrics derived from `Store.list_records` (full table scan)

| Endpoint | Scan Pattern | Time Filter |
|----------|-------------|-------------|
| `/api/uar/runs/failure-clusters` | All runs → events → errors | 24h default |
| `/api/uar/confidence-drift` | All runs → events → errors | 24h default |
| `/api/uar/topology/hot-paths` | All runs → skills + metadata.execution_order | 168h default |
| `/api/uar/topology/failure-hotspots` | All runs → skills + events → errors | 168h default |
| `/api/uar/recipes/intelligence` | All runs → metadata.execution_order + confidence | 168h default |

### Metrics derived from in-memory ring buffers

| Buffer | Endpoint | Size | Reset Behavior |
|--------|----------|------|----------------|
| `_MC_HISTORY` | `/api/uar/mission-control` (write)  
`/api/uar/mission-control/history` (read) | Max 100 | Server restart |
| `_BURNIN_HISTORY` | `/api/uar/burnin/history` (read)  
`/api/uar/burnin/run` (write) | Max 50 (implied by limit param) | Server restart |

### Metrics derived from direct record fetch

| Endpoint | Record Access | Aggregation |
|----------|-------------|-------------|
| `/api/uar/runs/{id}/explorer` | `get_by_run_id` | None (raw bundle) |
| `/api/uar/runs/{a}/compare/{b}` | `get_by_run_id` x2 | Diff only |

---

## Dependency Graph (Simplified)

```
RunRecord Store (SQLite/Postgres)
    │
    ├──► Mission Control ──► _MC_HISTORY ──► TrendPanel
    │       │
    │       └──► ConfidenceDriftPanel (also reads _MC_HISTORY + Store)
    │
    ├──► ReplayExplorer (direct record)
    ├──► CompareRuns (direct record x2)
    │
    ├──► FailureClusterPanel (full scan)
    ├──► FailureHotspotPanel (full scan)
    ├──► TopologyAnalyticsPanel (full scan)
    ├──► RecipeIntelligencePanel (full scan)
    │
    └──► BurnInHistory ◄── _BURNIN_HISTORY ◄── BurnInRunner

Registry (static config)
    └──► TopologyWidget (no execution data)
```

---

## Findings (Preliminary)

1. **Five endpoints perform full table scans** on every request (`failure-clusters`, `confidence-drift`, `hot-paths`, `failure-hotspots`, `recipes/intelligence`). All scan `Store.list_records()` and iterate events/skills. No database indexes are used; filtering is done in Python.

2. **Mission Control is the central data producer** for trends and drift. If MC is not polled, `_MC_HISTORY` remains empty and both `TrendPanel` and `ConfidenceDriftPanel` show empty states.

3. **No caching layer** exists between the store and any analytics endpoint. Every request re-aggregates from raw records.

4. **Replay Explorer and Compare Runs** are the only analytics features that do not aggregate. They read individual records and derive local metrics.

5. **Recipe intelligence and topology analytics** both consume `metadata.execution_order`, which was introduced in the unified order work. This is the only D-phase feature that depends on the newer metadata field.

6. **Burn-In history is entirely in-memory.** Restarting the server loses all burn-in trend data unless the operator explicitly triggers a new burn-in run.

---

## Next Steps

- Proceed to **Review B — Redundancy Analysis**
- Proceed to **Review C — Operator Journey**
- Proceed to **Review D — Performance Baseline**
