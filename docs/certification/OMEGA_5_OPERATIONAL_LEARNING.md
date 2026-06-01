# Omega-5: Operational Learning

**Phase**: Ω-5 (Operational Learning)
**Status**: Ω-5.1 Complete — Learning Layer Surfaced
**Committed**: `5acbd64`
**Date**: 2026-06-01

---

## Purpose

Omega-5 is the first phase in which UAR attempts to turn operational history into actionable guidance. Unlike all preceding phases, which focused on *recording*, *certifying*, and *reporting* what happened, Omega-5 introduces the ability to derive *what to do next* from accumulated operational memory.

The goal is not prediction, forecasting, or ML. It is structured, explainable recommendation from observed patterns.

---

## Architecture

### Information Flow

```
Execution
    ↓
Replay          → Authenticity
    ↓
Memory          → Governance
    ↓
Learning        → Operator
```

Before Ω-5.1, the chain terminated at Learning as an internal subsystem.
After Ω-5.1, Learning is exposed to the operator through a dedicated endpoint and panel.

### One Truth, Many Projections

Recommendations derive from the same shared truth sources as all other analytics:

| Projection | Source |
|------------|--------|
| Failure Clusters | `AnalyticsSnapshot.skill_clusters` |
| Confidence Drift | `AnalyticsSnapshot` + `_MC_HISTORY` + `_BURNIN_HISTORY` |
| Recipe Intelligence | `AnalyticsSnapshot.recipe_stats` |
| **Recommendations** | `AnalyticsSnapshot` + `MultiRunIntelligence` + `OperationalLearning` |

No separate data pipeline. No fork. All projections invalidate together.

### Source Hierarchy

```
AnalyticsSnapshot
    ├── total_failures / total_runs → governance approval_rate
    ├── topology_nodes / topology_edges → topology evolution
    └── (via extractors)

MultiRunIntelligence
    ├── find_recurring_failures()   → recurring patterns
    └── build_recovery_atlas()      → recovery paths

OperationalLearning
    ├── recommend_from_recurring_failures()
    ├── recommend_from_recovery_atlas()
    ├── recommend_from_topology_evolution()
    └── recommend_from_governance_trends()
```

Unified entry point: `generate_all_recommendations()`

---

## API

### Endpoint

`GET /api/uar/recommendations?hours={h}&limit={n}`

### Response Shape

```json
{
  "generated_at": 1717252800.0,
  "hours": 24,
  "runs_analyzed": 150,
  "recommendations": [
    {
      "category": "remediate",
      "priority": "critical",
      "confidence": 0.95,
      "title": "Recurring failure: timeout::a+b",
      "description": "Pattern 'timeout::a+b' has occurred 12 times...",
      "source": "recurrence_engine",
      "affected_runs": ["r1", "r2", ...]
    }
  ],
  "sources": {
    "recurring_patterns": 3,
    "recovery_paths": 5,
    "topology_points": 1,
    "governance_periods": 1
  }
}
```

### Categories

| Category | Meaning |
|----------|---------|
| `remediate` | Fix a known recurring issue |
| `investigate` | Dig deeper into a suspicious pattern |
| `optimize` | Improve efficiency or structure |
| `review` | Human review recommended |

### Priority Scale

| Priority | Threshold |
|----------|-----------|
| `critical` | ≥ 8 occurrences or 100% failure |
| `high` | ≥ 5 occurrences or ≥ 50% failure |
| `medium` | ≥ 3 occurrences or ≥ 25% failure |
| `low` | < 3 occurrences |

---

## Cache Behavior

Recommendations use `AnalyticsCache` with key `"recommendations"`, scoped by:

- `user`
- `is_admin`
- `hours`
- `limit`

### Invalidation

- `new run` → `runs.py` calls `_analytics_cache().invalidate()`
- `burn-in` → `burn_in.py` calls `_analytics_cache().invalidate()`
- `replay / certification` → read-only, no invalidation

This ensures recommendations remain globally consistent with all other analytics projections.

---

## Frontend: Operator-Action Panel

### Location

`apps/web/src/components/RecommendationPanel.tsx`

Wired into `MissionControlWidget` as a default-open collapsible section labeled **"Recommendations"**.

### Design Philosophy

Evidence first, recommendation second, action implied.

Each card displays:
- **Category icon + priority badge + source tag**
- **Title** (what the pattern is)
- **Description** (what the engine observed)
- **Evidence block** — occurrences, rate, confidence, suggested action
- **Affected runs count**

This structure preserves the evidence-first philosophy established in Ω-2 (Replay) and Ω-3 (Provenance).

---

## Verification

| Test Suite | Status |
|------------|--------|
| `tests/api/test_recommendations.py` | 4/4 passing |
| Full backend suite | 4203/4204 passing |
| TypeScript compilation | Clean |

The one pre-existing failure (`test_yolo_detect`) is outside this scope.

---

## Future Plan

### Ω-5.2 — Operator Feedback Loop

Add per-recommendation operator feedback:

- `Accept` — recommendation was useful and acted upon
- `Reject` — recommendation was incorrect or unhelpful
- `Dismiss` — recommendation is noise

Capture:
- `recommendation_id`
- `operator_action`
- `timestamp`

This creates:

```
Pattern → Recommendation → Human Judgment
```

the first true feedback channel between operational memory and operational behavior.

### Ω-5.3 — Recommendation Quality Metrics

| Metric | Meaning |
|--------|---------|
| Acceptance Rate | Was advice useful? |
| Dismissal Rate | Noise indicator |
| Time-to-Accept | Urgency signal |
| Recommendation Recurrence | Same advice appearing repeatedly |

### Ω-5.4 — Forecasting / Predictive Learning

Only after Ω-5.2 and Ω-5.3 establish that recommendations are themselves trustworthy.

---

## Design Decisions

### Why Not ML or LLMs Yet

The simpler path:

```
Observed Pattern → Human Recommendation
```

must be validated before attempting:

```
Observed Pattern → Predicted Future
```

ML and LLMs add opacity. The current heuristics are fully explainable, which aligns with the evidence-first philosophy of Ω-2 through Ω-4.

### Why Operator-Action Framing

A recommendation without evidence is an assertion.
A recommendation with evidence is an argument.

The operator must be able to evaluate the argument, not merely obey the assertion.

---

## Files

| File | Role |
|------|------|
| `uar/api/routers/mission_control.py` | `/api/uar/recommendations` endpoint |
| `uar/core/operational_learning.py` | Recommendation engine heuristics |
| `uar/core/multi_run_intelligence.py` | Pattern extraction |
| `apps/web/src/components/RecommendationPanel.tsx` | Operator UI panel |
| `apps/web/src/components/RecommendationPanel.module.css` | Panel styles |
| `apps/web/src/components/MissionControlWidget.tsx` | Widget integration |
| `tests/api/test_recommendations.py` | API tests |

---

## Classification

At Ω-2: **Certified Runtime**
At Ω-4C: **Governed Runtime**
At Ω-5.1: **Operational Intelligence Runtime**

The system is no longer merely reporting what happened. It generates actionable guidance from accumulated history and surfaces that guidance to operators.
