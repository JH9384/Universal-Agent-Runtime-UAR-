---
description: Prevent unbounded memory growth from caches, registries, and pools without size limits or eviction
tags: [backend, cache, memory, performance, python]
---

# Rule: Bounded Caches and Registries

## Problem

Any global or instance-level `Dict` / `List` / `OrderedDict` that grows with every new key without size limits or eviction becomes a **slow memory leak**. In long-running processes (FastAPI/uvicorn workers), this accumulates indefinitely.

Common failure modes:

1. **Global module-level caches** — e.g., per-domain HTTP sessions keyed by hostname
2. **Instance-level content-addressed caches** — e.g., vector caches keyed by digest
3. **Connection pools without caps** — unbounded DB or HTTP connection growth
4. **Registry dicts** — e.g., circuit breaker registry (bounded by decorator usage, still worth capping)

## Detection

Flag any of the following:

- Module-level: `_cache: Dict[...] = {}` or `_sessions: Dict[...] = {}` with no `_MAX_*` constant
- Instance-level: `self._cache: Dict[...] = {}` in `__init__` with no `maxsize` or eviction
- `while` / `if` checks that grow a collection without pruning
- `.append()`, `.update()`, or direct assignment (`d[k] = v`) on caches with no eviction path

## Prevention

### Add a `_MAX_*` bound with FIFO eviction

**Bad:**

```python
# Module level
_sessions: Dict[str, Any] = {}

async def _get_session(url: str):
    domain = urlparse(url).netloc
    if domain in _sessions:
        return _sessions[domain]
    sess = aiohttp.ClientSession(...)
    _sessions[domain] = sess  # grows forever
    return sess
```

**Good:**

```python
import collections

_sessions: "collections.OrderedDict[str, Any]" = collections.OrderedDict()
_MAX_SESSIONS = max(
    1,
    min(256, int(os.getenv("UAR_HTTP_MAX_SESSIONS", "32").strip() or "32")),
)

async def _get_session(url: str):
    domain = urlparse(url).netloc
    try:
        return _sessions[domain]
    except KeyError:
        pass
    async with _session_lock:
        if domain in _sessions:
            return _sessions[domain]
        # Evict oldest if at capacity
        while len(_sessions) >= _MAX_SESSIONS:
            oldest_domain, oldest_sess = _sessions.popitem(last=False)
            try:
                await oldest_sess.close()
            except Exception:
                logger.exception("Session close failed for %s", oldest_domain)
        sess = aiohttp.ClientSession(...)
        _sessions[domain] = sess
        return sess
```

### Instance-level caches

**Bad:**

```python
class UORVectorOps:
    def __init__(self):
        self.vector_cache: Dict[str, UORVector] = {}

    def create_vector(self, data):
        vector = UORVector(data)
        vector.compute_digest()
        self.vector_cache[vector.digest] = vector  # grows forever
        return vector
```

**Good:**

```python
class UORVectorOps:
    def __init__(self):
        self._max_cache_size = max(
            1,
            int(os.getenv("UAR_VECTOR_CACHE_SIZE", "1000").strip() or "1000"),
        )
        self.vector_cache: Dict[str, UORVector] = {}

    def create_vector(self, data):
        vector = UORVector(data)
        vector.compute_digest()
        if vector.digest:
            while len(self.vector_cache) >= self._max_cache_size:
                self.vector_cache.pop(next(iter(self.vector_cache)), None)
            self.vector_cache[vector.digest] = vector
        return vector
```

## Checklist

- [ ] Every global module-level dict cache has a `_MAX_*` constant and eviction logic
- [ ] Every instance-level cache has a `maxsize` with FIFO or LRU eviction
- [ ] Eviction closes or cleans up resources (sessions, connections, files) before dropping the reference
- [ ] Use `collections.OrderedDict` when `popitem(last=False)` is needed for true FIFO
- [ ] Bounds are configurable via environment variables with sensible defaults
- [ ] The bound is enforced **before** insertion, not lazily or only at shutdown
