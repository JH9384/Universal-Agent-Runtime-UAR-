---
description: Prevent use-after-close races when evicting resources from caches or pools
globs: uar/**/*.py
---

# Resource Eviction Race Prevention

## Rule

When a cache or pool evicts and closes/destructs resources, **do not perform the close/destroy while holding the lock** if other code accesses those resources on a fast path **without** the lock.

## Why

A common pattern:

```python
async with _lock:
    if key in _cache:
        return _cache[key]  # fast path inside lock — OK
    # slow path: evict oldest
    oldest = _cache.popitem()
    await oldest.close()   # BAD: close under lock
    _cache[key] = new_item
```

Another coroutine may have already obtained `oldest` on the fast path (before we acquired the lock) and is about to use it. Closing it under the lock causes a **use-after-close** crash.

## Correct Pattern

```python
to_close = []
async with _lock:
    if key in _cache:
        return _cache[key]
    while len(_cache) >= MAX:
        _, item = _cache.popitem()
        to_close.append(item)
    _cache[key] = new_item
for item in to_close:
    await item.close()   # close AFTER releasing lock
```

## Applies To

- aiohttp / httpx session caches
- connection pools (DB, HTTP)
- any bounded cache with eviction
- both `asyncio.Lock` and `threading.Lock`
