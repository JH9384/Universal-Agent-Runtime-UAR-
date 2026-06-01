# list_records Usage Audit

## D4A-0 — Run Cap Resolution
**Date:** 2026-06-01  
**Commit Base:** 57ed78b  
**Status:** Complete

---

## Store Interface

```python
def list_records(
    self,
    user_id: Optional[str] = None,
    limit: int = 1000,        # <-- the silent cap
) -> List[Dict[str, Any]]:
```

**Default limit by backend:**
- `SqliteRunStore`: 1,000
- `JsonRunStore`: 1,000
- `PostgresRunStore`: 100

**Note:** Postgres has a *different* default (100 vs 1,000). This is an additional consistency issue.

---

## Call Site Inventory

### Backend — API Routers

| # | File | Line | Endpoint | Limit Used | Type | Purpose |
|---|------|------|----------|------------|------|---------|
| 1 | `uar/api/routers/runs.py` | 280 | `GET /api/uar/runs` | default (1,000) | **Operational** | Runs history list |
| 2 | `uar/api/routers/runs.py` | 777 | `GET /api/uar/runs/failure-clusters` | default (1,000) | **Analytics** | Failure clustering |
| 3 | `uar/api/routers/runs.py` | 898 | `GET /api/uar/topology/hot-paths` | default (1,000) | **Analytics** | Topology usage |
| 4 | `uar/api/routers/runs.py` | 1032 | `GET /api/uar/topology/failure-hotspots` | default (1,000) | **Analytics** | Topology failure overlay |
| 5 | `uar/api/routers/recipes.py` | 155 | `GET /api/uar/recipes/intelligence` | default (1,000) | **Analytics** | Recipe performance |
| 6 | `uar/api/routers/mission_control.py` | 174 | `GET /api/uar/confidence-drift` | default (1,000) | **Analytics** | Drift contributors |

### Backend — Core / Store

| # | File | Line | Caller | Limit Used | Type | Purpose |
|---|------|------|--------|------------|------|---------|
| 7 | `uar/core/runtime_health.py` | 105 | `build_runtime_snapshot()` | `limit=500` (param) | **Operational** | Health snapshot for MC |
| 8 | `uar/memory/json_store.py` | 130 | `JsonRunStore.get_by_run_id()` | default (1,000) | **Operational** | Find single record by ID |

---

## Classification

### Operational Usage (safe with cap)

- **Runs history (`/api/uar/runs`)** — Showing the most recent 1,000 runs is reasonable for a UI list. Pagination could be added later.
- **`build_runtime_snapshot()`** — Explicitly passes `limit=500` for a health snapshot. The caller controls the scope.
- **`JsonRunStore.get_by_run_id()`** — Loads all records to find one. This is a store-level inefficiency, not an analytics cap issue. The JSON store is a fallback; SQLite/Postgres use indexed lookup.

### Analytics Usage (cap is dangerous)

All five analytics endpoints:
- `failure-clusters`
- `hot-paths`
- `failure-hotspots`
- `recipes/intelligence`
- `confidence-drift`

**Why dangerous:**
- They aggregate over a time window (hours, default 24–168).
- If the operator has >1,000 runs in the store, only the 1,000 most recent are loaded.
- If the time window extends beyond the 1,000 most recent runs, the analysis silently omits older data.
- The response includes `total_runs` or `total_runs_scanned`, but this is the count of *filtered* runs, not the count of *available* runs.

**Example scenario:**
- Operator has 10,000 runs over 30 days.
- `failure-clusters` with `hours=168` (7 days) loads 1,000 most recent runs.
- If the 1,000 most recent runs span only 3 days, runs from days 4–7 are silently excluded.
- The response says `"total_runs_scanned": 847` — the operator assumes this is the full 7-day window.

---

## Resolution Applied

### Analytics Endpoints

Each analytics endpoint now:
1. Accepts an explicit `limit` query parameter (default 1,000, max 50,000).
2. Passes that limit to `store.list_records()`.
3. Returns metadata about the dataset actually analyzed:

```json
{
  "meta": {
    "runs_loaded": 1000,
    "runs_analyzed": 847,
    "limit": 1000,
    "truncated": true
  }
}
```

**Fields:**
- `runs_loaded`: Records returned by the store query.
- `runs_analyzed`: Records that passed the time filter.
- `limit`: The cap that was applied.
- `truncated`: `true` if `runs_loaded == limit`, indicating the cap may have been hit.

### Operational Endpoints

No change. The runs history endpoint retains the default 1,000 cap because:
- It is a list view, not an aggregate.
- The UI can paginate or request more if needed.

---

## Postgres Inconsistency Note

`PostgresRunStore.list_records` defaults to `limit=100` while SQLite and JSON default to `limit=1000`.

**Impact:** If the deployment switches from SQLite to Postgres, analytics accuracy drops by 10x silently.

**Resolution:** Postgres default should be aligned to 1,000 or made explicitly configurable per-deployment. This is noted as a follow-up item, not part of D4A-0.

---

## Files Modified

- `uar/api/routers/runs.py` — 3 endpoints
- `uar/api/routers/recipes.py` — 1 endpoint
- `uar/api/routers/mission_control.py` — 1 endpoint
