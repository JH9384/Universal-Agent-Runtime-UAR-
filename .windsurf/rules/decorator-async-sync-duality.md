---
description: Decorators must preserve the async/sync nature of the wrapped function
tags: [bug-pattern, decorators, async, python]
globs: ["uar/core/*.py", "uar/api/*.py"]
---

# Decorator Async/Sync Duality Rule

## Rule

Any decorator that **wraps a callable** (i.e., defines its own `wrapper` function and returns it) MUST inspect the wrapped function for async-ness and provide both a sync and async wrapper.

**Never** write a decorator that unconditionally returns a synchronous `def wrapper(...)` when the decorated function might be `async def`.

## Why

If an `async def` function is wrapped by a sync-only decorator, calling the decorated function returns a **coroutine object** without awaiting it. The function body never executes, and the caller receives a raw coroutine instead of the expected result. This is a silent failure that breaks executor logic, API endpoints, and skill pipelines.

## Detect

Forbidden pattern — sync-only wrapper on a potentially-async function:

```python
from functools import wraps

def my_decorator(...):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):  # ← broken for async funcs
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

Correct pattern — dual sync/async wrappers:

```python
import inspect
from functools import wraps

def my_decorator(...):
    def decorator(func):
        if inspect.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                return await func(*args, **kwargs)
            return async_wrapper

        @wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator
```

## Known Offenders (Fixed)

- `uar/core/retry_decorator.py::with_retry` — only defined sync `wrapper`; async skills never retried.
- `uar/core/skill_cache.py::cached_skill` — only defined sync `wrapper`; async skills returned unawaited coroutine.
- `uar/core/registry.py::requires_package` — only defined sync `wrapper`; async skills returned unawaited coroutine.

## Correct Examples in Codebase

- `uar/core/skill_utils.py::skill_guard` — correctly checks `inspect.iscoroutinefunction(fn)` and provides both wrappers.
- `uar/core/circuit_breaker_decorator.py::with_circuit_breaker` — correctly checks `inspect.iscoroutinefunction(func)` and provides both wrappers.

## Exception

API-layer decorators in `uar/api/` that are exclusively used on FastAPI route handlers may remain async-only **only if** the codebase guarantees 100% async usage at that layer.
