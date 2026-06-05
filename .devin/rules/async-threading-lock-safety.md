---
description: Never use threading.Lock or threading.RLock in async contexts without async_lock
tags: [bug-pattern, async, threading, concurrency, python]
globs: ["uar/**/*.py"]
---

# Async Threading Lock Safety Rule

## Rule

In **any `async def` function** (or async decorator wrapper), **NEVER** acquire a `threading.Lock()` or `threading.RLock()` with a plain `with lock:` block.

Use :func:`uar.core.async_utils.async_lock` instead, which dispatches lock acquisition to a thread pool so the event loop stays free.

## Why

`threading.Lock.acquire()` is a blocking syscall. When called from the async event loop thread (e.g., inside a FastAPI handler or an async skill wrapper), it:

- Freezes the event loop for the duration of the critical section
- Prevents other concurrent requests, heartbeats, and timeouts from firing
- Under high load, turns microsecond lock holds into millisecond latency spikes
- Can cause cascading timeouts and circuit breaker false positives

## Detect

Forbidden pattern in async code:

```python
async def my_async_fn():
    with some_threading_lock:          # ← blocks event loop
        mutate_shared_state()
```

Correct pattern — use `async_lock` context manager:

```python
from uar.core.async_utils import async_lock

async def my_async_fn():
    async with async_lock(some_threading_lock):
        mutate_shared_state()
```

## Critical Locations

Any of the following async contexts are especially vulnerable:

- **Circuit breaker** `call_async()` implementations — state transitions under lock
- **Global registry** read/write methods called from FastAPI endpoints (`get_circuit_breaker_states`, `reset_circuit_breaker`)
- **Skill cache** async wrappers (`cached_skill`) — LRU cache get/set
- **Metrics collector** `record_request` calls from `@timed` async wrapper
- **Rate limiter** `is_allowed()` when called directly from async endpoints
- **Authentication middleware** `_api_keys_lock` when called from async handlers

## Known Offenders (Fixed)

- `uar/core/circuit_breaker.py::call_async` — used `with self._lock:` inside async method
- `uar/core/circuit_breaker_decorator.py::get_circuit_breaker_states` — used `with _circuit_breakers_lock:` in async endpoint path
- `uar/core/circuit_breaker_decorator.py::reset_circuit_breaker` — used `with _circuit_breakers_lock:` in async endpoint path
- `uar/core/skill_cache.py::cached_skill` async wrapper — `cache.get()`/`cache.set()` acquired `threading.RLock()` directly
- `uar/api/metrics.py::timed` async wrapper — `collector.record_request()` acquired `threading.Lock()` directly

## Exceptions

- **Thread-pool workers** (e.g., `ThreadPoolExecutor` callbacks, `run_in_executor` targets) already run on non-event-loop threads, so `with lock:` is safe there.
- **Synchronous generators** like `Executor.iter_events()` that are consumed via `run_in_executor` or `run_sync_safe` may use `threading.Lock` because they execute in a worker thread, not the event loop.
- **Module import time** (e.g., decorator factory registering a circuit breaker) runs before the event loop exists, so direct `threading.Lock` usage is fine.

## Helper

```python
from uar.core.async_utils import async_lock

# Use wherever a threading.Lock must be acquired from async code
async with async_lock(my_lock):
    ...
```
