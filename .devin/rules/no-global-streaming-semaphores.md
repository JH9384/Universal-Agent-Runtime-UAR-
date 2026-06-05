---
description: Never use module-level asyncio.Semaphore for per-request streaming limits
tags: [bug-pattern, async, streaming, backpressure, python]
globs: ["uar/**/*.py"]
---

# No Global Streaming Semaphores Rule

## Rule

An `asyncio.Semaphore` that limits in-flight events, backpressure, or any other **per-request / per-stream** resource MUST be created per-request, not at module level.

**Forbidden:**
```python
# Module-level semaphore shared across ALL requests
_backpressure_sem = asyncio.Semaphore(1000)

async def stream_events():
    await _backpressure_sem.acquire()
    try:
        yield event
    finally:
        _backpressure_sem.release()
```

**Correct:**
```python
async def stream_goal(...):
    bp_sem = asyncio.Semaphore(_BACKPRESSURE_LIMIT)
    async for event in self._iter_events(..., bp_sem):
        yield event

async def _iter_events(..., bp_sem: asyncio.Semaphore):
    await bp_sem.acquire()
    try:
        yield event
    finally:
        bp_sem.release()
```

## Why

A module-level semaphore creates **cross-request head-of-line blocking**. One slow consumer exhausts the global limit, causing every other concurrent stream to stall even though their consumers are fast. The limit is meant to protect a single slow consumer from OOM, not to throttle the entire server.

## Detect

Look for `asyncio.Semaphore` assigned at module scope (not inside a class `__init__` or function body) when the semaphore is acquired inside an async generator or streaming handler.

## Exception

A module-level semaphore is acceptable ONLY when the resource is genuinely global (e.g., total DB connection pool, total WebSocket connection cap). Per-request or per-stream resources must be request-scoped.
