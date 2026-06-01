# Issue #85 — Runtime Health Query Consolidation

Status: Open
Priority: P1
Phase: Trust Spine Hardening
Depends on: T2 (Runtime Health), T5 (Mission Control)

## Problem

A single `GET /api/uar/mission-control` request currently triggers
four independent store scans:

1. `score_runtime_health` → `store.list_records(limit=500)` (execution
   component scoring)
2. `build_snapshot` → `store.list_records(limit=1)` (replay confidence
   from most recent run)
3. `build_snapshot` → `store.list_records(limit=500)` (active run count)
4. `get_certification` (if called separately) → `store.list_records(limit=1)`

At low volume this is acceptable. Under production load with a large
store it becomes a bottleneck: each scan is a full SQLite table read
with no status-based index.

## Root Cause

`score_runtime_health`, `build_snapshot`, and the active-run counter
each independently query the store because they were built as
standalone pure functions. There is no shared snapshot object passed
between them.

## Goal

Replace the 4 independent queries with a single `RuntimeSnapshot`
query that loads the data once and passes it to all consumers.

## Proposed Design

```python
@dataclass
class RuntimeSnapshot:
    """Single-pass store read shared across all scoring functions."""
    recent_records: List[dict]   # last N records (configurable)
    active_count: int            # records with status in running/pending/queued
    latest_record: Optional[dict]
    queried_at: float
```

Introduce `build_runtime_snapshot(store, limit=500) -> RuntimeSnapshot`
in `uar/core/runtime_health.py`.

Update signatures:

- `score_runtime_health(snapshot, registry, burnin_report)`
- `build_snapshot(snapshot, registry, burnin_report)` in
  `mission_control.py`

The API routers call `build_runtime_snapshot` once and pass the result
to all downstream functions.

## Acceptance Criteria

- `GET /api/uar/mission-control` issues exactly one `list_records` call
  to the store per request
- All existing `test_runtime_health.py` and `test_mission_control.py`
  tests continue to pass
- New test in `tests/api/test_trust_spine_fixes.py` verifies store is
  called exactly once (use `unittest.mock.patch`)

## Out of Scope

- Caching/TTL across requests (follow-on work)
- Async store adapters
