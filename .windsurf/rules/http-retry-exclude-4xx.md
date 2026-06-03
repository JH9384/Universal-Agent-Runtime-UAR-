---
description: HTTP retry logic must exclude non-retryable 4xx client errors
globs: uar/**/*.py
---

# HTTP Retry: Exclude 4xx Client Errors

## Rule

Any retry/backoff loop around HTTP requests MUST skip retries for **4xx client errors** (`400 <= status < 500`). These are deterministic failures; retrying them wastes resources and may trigger rate limits.

## Why

```python
# BAD — retries on 404, 403, 401, etc.
for attempt in range(max_retries):
    try:
        resp = await session.get(url)
        resp.raise_for_status()
    except Exception as exc:
        # Retries everything including 404
        await asyncio.sleep(backoff)
```

A `404 Not Found` or `403 Forbidden` will never succeed on retry. The server has explicitly refused the request.

## Correct Pattern

```python
def _is_client_error(exc: BaseException) -> bool:
    status = getattr(exc, "status", None)
    return isinstance(status, int) and 400 <= status <= 499

for attempt in range(max_retries):
    try:
        resp = await session.get(url)
        resp.raise_for_status()
    except Exception as exc:
        if _is_client_error(exc):
            raise
        # Only retry transient errors (5xx, network, timeout)
        await asyncio.sleep(backoff)
```

## Edge Cases

- `429 Too Many Requests` is technically a 4xx but MAY be retried with care (respect `Retry-After` header). Treat it separately if your code handles it.
- `409 Conflict` and `410 Gone` are also deterministic — do not retry.
