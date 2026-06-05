---
description: except Exception in async contexts must re-raise asyncio.CancelledError
tags: [bug-pattern, async, python, exceptions]
globs: ["uar/**/*.py"]
---

# Async CancelledError Re-raise Rule

## Rule

In **any `async def` function** (or async decorator wrapper), an `except Exception:` block MUST explicitly re-raise `asyncio.CancelledError` **before** the generic catch.

**Never** let `except Exception:` swallow `asyncio.CancelledError` silently.

## Why

Since Python 3.8, `asyncio.CancelledError` is a subclass of `Exception`. An unqualified `except Exception:` will catch it, preventing task cancellation from propagating. This causes:

- Tasks that should stop to keep running
- Server shutdown sequences to hang
- Timeout mechanisms to fail
- Circuit breakers to incorrectly count cancellations as service failures

## Detect

Forbidden pattern in async code:

```python
async def some_function():
    try:
        await do_work()
    except Exception:
        logger.warning("Failed")
        return None
```

Correct pattern:

```python
async def some_function():
    try:
        await do_work()
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.warning("Failed")
        return None
```

## Critical Locations

Any of the following async contexts are especially vulnerable:

- **Decorators** that wrap async functions (`skill_guard`, `api_error_handler`, `error_handler_middleware`, `timed`, `with_retry`)
- **Retry loops** that catch and retry on exceptions
- **Long-running async loops** (heartbeat, polling, background tasks)
- **Circuit breaker** `call_async` implementations

## Known Offenders (Fixed)

- `uar/core/skill_utils.py::skill_guard` async wrapper — swallowed `CancelledError` and returned error dict
- `uar/api/middleware.py::error_handler_middleware` — converted `CancelledError` to HTTP 500
- `uar/api/middleware.py::api_error_handler` — converted `CancelledError` to HTTP 500
- `uar/uor/async_resolution.py::fetch_object` — returned `None` on cancellation instead of propagating
- `uar/uor/async_resolution.py::fetch_with_retry` — retried on `CancelledError` instead of stopping
- `uar/core/retry_decorator.py::with_retry` async wrapper — could retry on `CancelledError` if caller passed `Exception` in `retry_on`
- `uar/core/circuit_breaker.py::call_async` — counted `CancelledError` as a service failure, potentially opening the circuit

## Exception

In **FastAPI route handlers**, the ASGI server typically handles client disconnects by cancelling the task *before* the handler code runs, so `CancelledError` rarely reaches the handler directly. However, explicit re-raise is still defensive and recommended.
