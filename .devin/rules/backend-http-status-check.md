---
description: Prevent silent acceptance of HTTP error responses in backend async/sync HTTP clients
tags: [backend, http, aiohttp, httpx, requests, python]
---

# Rule: Backend HTTP Status Validation

## Problem

Backend HTTP wrappers that call `.json()` without first checking the HTTP status code will **silently return error payloads as successful results**. A 500 Internal Server Error that returns JSON becomes indistinguishable from a 200 OK with JSON.

This is especially dangerous in retry loops where the caller believes the request succeeded and never retries.

## Detection

Flag any code that:

1. Calls `resp.json()` on an HTTP response without `resp.raise_for_status()` first
2. Has a retry loop that catches all exceptions but never validates HTTP status
3. Returns the result of `await resp.json()` directly without status checks

## Prevention

### aiohttp (async)

**Bad:**

```python
async def http_get(url: str) -> Any:
    async with session.get(url) as resp:
        return await resp.json()  # 500 with JSON → returned as success
```

**Good:**

```python
async def http_get(url: str) -> Any:
    async with session.get(url) as resp:
        resp.raise_for_status()  # raises ClientResponseError on 4xx/5xx
        return await resp.json()
```

### httpx (sync or async)

**Bad:**

```python
resp = client.get(url)
return resp.json()  # No status check
```

**Good:**

```python
resp = client.get(url)
resp.raise_for_status()  # raises HTTPStatusError on 4xx/5xx
return resp.json()
```

### requests (sync)

**Bad:**

```python
resp = requests.get(url)
return resp.json()  # No status check
```

**Good:**

```python
resp = requests.get(url)
resp.raise_for_status()  # raises HTTPError on 4xx/5xx
return resp.json()
```

### Retry loops

When using `raise_for_status()` inside a retry loop, the retry logic will catch the status exception and retry. This is usually correct for 5xx (server errors) but wasteful for 4xx (client errors). Consider separating retryable vs non-retryable status codes:

```python
from aiohttp import ClientResponseError

for attempt in range(_MAX_RETRIES):
    try:
        async with session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()
    except ClientResponseError as exc:
        if exc.status < 500:
            raise  # Don't retry 4xx client errors
        if attempt == _MAX_RETRIES - 1:
            raise
        await asyncio.sleep(delay)
```

## Checklist

- [ ] Every backend HTTP wrapper calls `raise_for_status()` (or equivalent) before parsing the response body
- [ ] Retry loops distinguish between 4xx (client error, don't retry) and 5xx (server error, retry)
- [ ] Error responses that contain JSON error details are properly surfaced as exceptions, not returned as success
- [ ] Test cases verify that non-2xx responses raise rather than returning the error JSON
