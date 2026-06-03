---
description: Serialization / deep-copy fallbacks must raise, not silently return empty data
tags: [bug-pattern, data-integrity, serialization, python]
globs: ["uar/**/*.py"]
---

# No Silent Serialization Fallbacks Rule

## Rule

Any function that serializes, copies, or snapshots data for isolation (parallel execution, retry, persistence) MUST raise an exception on complete failure. It MUST NOT log a warning and return an empty/default value.

**Forbidden:**
```python
def snapshot_context(data):
    try:
        return pickle.dumps(data)
    except Exception:
        logger.warning("Pickle failed, returning empty dict")
        return {}  # ← Silent data loss
```

**Correct:**
```python
def snapshot_context(data):
    try:
        return pickle.dumps(data)
    except Exception as exc:
        raise RuntimeError("Context snapshot failed") from exc
```

## Why

Returning `{}`, `[]`, `None`, or any default value on serialization failure causes **silent data loss**. In parallel execution, the skill receives an empty context and produces incorrect results. In retry logic, the snapshot is worthless and the retry wastes resources. In persistence, the stored record is incomplete.

## Detect

Search for `except Exception:` (or broad catch) in functions named `snapshot`, `serialize`, `copy`, `clone`, `dumps`, `deepcopy` where the fallback returns `{}`, `[]`, `None`, `""`, or any default-constructed value.

## Exception

A graceful fallback is acceptable when the caller explicitly checks for the sentinel value and handles it (e.g., `cache.get()` returning `None` to indicate a cache miss). The sentinel MUST be distinguishable from valid data.
