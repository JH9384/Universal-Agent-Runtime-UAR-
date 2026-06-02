# Mission Control Audit — 2026-06-01

## Executive Summary

The Trust Spine backend is complete. The frontend is not. Only **one** Trust Spine
signal (skill/circuit-breaker health) reaches the UI, and it uses the legacy
`/api/health/dashboard` endpoint rather than the new Trust Spine APIs.

## Widget Matrix

| Widget | Backend Module | API Endpoint | Frontend Component | Status |
|--------|---------------|-------------|-------------------|--------|
| Runtime Health | `uar/core/runtime_health.py` | `GET /api/uar/health/runtime` | **None** | 🔴 Missing |
| Replay Confidence | `uar/core/replay_confidence.py` | `GET /api/uar/runs/{run_id}/confidence` | **None** | 🔴 Missing |
| Certification | `uar/core/certification.py` | `GET /api/uar/certification` | **None** | 🔴 Missing |
| Burn-In Status | `uar/testing/burnin/runner.py` | `GET /api/uar/burnin/latest` | **None** | 🔴 Missing |
| Alerts / Warnings | `uar/core/mission_control.py` | `GET /api/uar/mission-control` | **None** | 🔴 Missing |
| Active Runs | `uar/core/mission_control.py` | `GET /api/uar/mission-control` | Partial (runs history list) | 🟡 Incomplete |

## API Inventory (All Mounted)

```
/api/uar/mission-control          → MissionControlSnapshot (T1+T2+T4 aggregate)
/api/uar/health/runtime           → RuntimeHealthReport (T2)
/api/uar/certification            → CertificationReport (T4)
/api/uar/burnin/latest            → BurnInReport (T3)
/api/uar/burnin/run               → Trigger smoke burn-in (POST)
/api/uar/runs/{run_id}/confidence → ReplayConfidenceReport (T1)
/api/uar/runs/{run_id}/explorer   → ReplayExplorer bundle (T6)
/api/health/dashboard             → Legacy skill/circuit-breaker health
```

## Frontend Inventory

### Existing Components

| Component | Purpose | Trust Spine Relevance |
|-----------|---------|----------------------|
| `UARPanel.tsx` | Main operator panel | Contains toggle for old HealthDashboard only |
| `HealthDashboard.tsx` | Skill availability + circuit breakers | **Legacy** — uses `/api/health/dashboard`, not `/api/uar/health/runtime` |
| `RecipeTimeline.tsx` | Recipe execution timeline | Could be extended for Replay Explorer |
| `MetricsDashboard.tsx` | Event metrics display | Operational, not Trust Spine |

### Missing Components

| Component | Needed For |
|-----------|-----------|
| `MissionControlWidget.tsx` | Single-widget Trust Spine summary |
| `RuntimeHealthCard.tsx` | Score, tier, component breakdown |
| `ReplayConfidenceCard.tsx` | Score, tier, warnings per run |
| `CertificationBadge.tsx` | Gold/Silver/Experimental badge |
| `BurnInStatus.tsx` | Last run, pass/fail, trigger button |
| `ReplayExplorer.tsx` | Run timeline, events, failure path |
| `ActiveRunsList.tsx` | Running/pending/queued runs |

## Data Contracts (Backend → Frontend)

### MissionControlSnapshot

```json
{
  "replay_confidence": { "score": 92, "tier": "High", "warnings": [] },
  "runtime_health": { "score": 88, "tier": "Healthy", "components": {...} },
  "certification": { "score": 90, "level": "Silver", "evidence": {...} },
  "active_runs": 3,
  "recent_warnings": ["runtime_health: store slow"],
  "timestamp": 1717200000.0
}
```

### ReplayExplorer Bundle

```json
{
  "run_id": "abc-123",
  "summary": { "status": "completed", "skills": [...] },
  "timeline": { ... },
  "confidence": { "score": 92, "tier": "High" },
  "failure_path": [{ "type": "error", ... }],
  "events": [...]
}
```

## Gap Analysis

| Gap | Impact | Effort |
|-----|--------|--------|
| No Mission Control widget | Operator cannot see system trust status at a glance | Medium (1 component) |
| No Runtime Health card | Operator cannot see health score/tier | Low (1 component) |
| No Replay Confidence card | Operator cannot assess run quality | Low (1 component) |
| No Certification badge | Operator cannot see release readiness | Low (1 component) |
| No Burn-In trigger/status | Cannot run or view burn-in from UI | Medium (1 component + API call) |
| No Replay Explorer | Cannot inspect run timeline/events visually | High (multi-panel component) |
| Legacy HealthDashboard still used | Confusing duplication; old endpoint lacks Trust Spine signals | Low (replace or redirect) |

## Recommendation

1. **Replace** the old `HealthDashboard` toggle in `UARPanel` with a
   `MissionControlWidget` that calls `/api/uar/mission-control`.
2. **Add** a `ReplayExplorer` route/panel for run drill-down.
3. **Deprecate** `/api/health/dashboard` or make it a thin wrapper
   around `score_runtime_health`.

## Issue #1–9 Relevance

Issues #1–9 are all UI/frontend gaps. This audit confirms they are the
**correct next priority** because every backend capability they need
already exists and is tested.
