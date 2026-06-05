---
description: CPU-heavy sync analytics must run in threadpool inside async handlers
tags: [async, performance, analytics, fastapi, threading]
---

# Sync Analytics Threadpool Rule

## Problem
FastAPI endpoints declared with `async def` run on the event loop. Calling CPU-intensive synchronous functions (data aggregation, graph analysis, statistical computation) blocks the entire loop, stalling all concurrent requests.

## Forbidden Pattern
```python
@router.get("/api/uar/recommendations")
async def get_recommendations(...):
    # BLOCKS the event loop — CPU-bound sync call
    snap = build_analytics_snapshot(recent_runs, user, is_admin, hours, limit)
    recommendations = generate_all_recommendations(...)
    trust_result = compute_trust(outcomes, metadata)
    return result
```

## Required Pattern
```python
from starlette.concurrency import run_in_threadpool

@router.get("/api/uar/recommendations")
async def get_recommendations(...):
    # Offloaded to worker thread — event loop stays free
    snap = await run_in_threadpool(
        build_analytics_snapshot, recent_runs, user, is_admin, hours, limit
    )
    recommendations = await run_in_threadpool(
        generate_all_recommendations, ...
    )
    trust_result = await run_in_threadpool(compute_trust, outcomes, metadata)
    return result
```

## Enforcement
- In any `async def` endpoint, sync functions that iterate over large datasets, compute aggregations, or perform statistical analysis MUST be wrapped with `run_in_threadpool`.
- Functions that ONLY do I/O (DB queries via async ORM, HTTP requests via aiohttp) do NOT need wrapping.
- When in doubt, wrap it. The overhead of `run_in_threadpool` is negligible compared to blocking the event loop.

## Rationale
Python's asyncio uses a single event loop per thread. A CPU-bound synchronous call blocks every concurrent coroutine. `run_in_threadpool` moves the work to a thread-pool executor, allowing the event loop to continue serving other requests.

## Common Offenders in UAR
- `build_analytics_snapshot(...)`
- `build_snapshot(...)` / `build_runtime_snapshot(...)`
- `compute_trust(...)` / `compute_effectiveness(...)` / `compute_calibration(...)`
- `generate_all_recommendations(...)`
- `find_recurring_failures(...)` / `build_recovery_atlas(...)`
- `extract_confidence_drift(...)` / `extract_failure_hotspots(...)` / `extract_recipe_intelligence(...)`
