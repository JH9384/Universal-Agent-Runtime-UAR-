---
description: Detect and remove dead counter / accumulator fields
tags: [dead-code, maintenance, fields]
---

# Dead Counter / Accumulator Field Anti-Pattern

## Rule

Fields that are **written to** (incremented, decremented, or assigned) but **never read** in production code must be removed. They confuse maintainers into thinking a feature exists that does not.

## Why

- **Misleading signal**: A `_pending_calls` counter suggests the system tracks in-flight operations, but if no dashboard, API, or logic queries it, the signal is a lie.
- **Maintenance burden**: Future developers add features around the dead field (metrics, UIs, new logic) only to discover it was never wired up.
- **Test bloat**: Dead fields accumulate tests that assert on implementation details rather than behavior.

## Detect

Look for instance attributes that match all three criteria:

1. **Initialized** in `__init__` or at module level.
2. **Mutated** in method bodies (e.g., `+= 1`, `-= 1`, assignment).
3. **Never read** outside of tests or debug logging.

Common patterns:

```python
# Module-level
_request_count = 0   # incremented but never queried

def handle():
    global _request_count
    _request_count += 1   # ← dead if no read site exists

# Instance-level
class Worker:
    def __init__(self):
        self._pending = 0   # ← dead if never read

    def submit(self, task):
        self._pending += 1
        ...
        self._pending -= 1   # ← write-only, no read
```

## Fix

**Remove the field entirely**, including:

- The declaration / initialization.
- Every increment / decrement / assignment.
- Every test that asserts on the removed field.
- Every docstring that references the removed field.

If the counter *should* be exposed, wire it up properly:

```python
@property
def pending_calls(self) -> int:
    with self._lock:
        return self._pending_calls
```

And add it to the API / dashboard / metrics layer.

## Known Offenders (Fixed)

- `uar/core/circuit_breaker.py::CircuitBreaker._pending_calls` — removed.

## Related Patterns

- `global-registry-param-shadowing.md` — global mutable state.
- `duplicate-routes-dead-code.md` — unreachable code paths.
