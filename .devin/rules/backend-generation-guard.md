---
description: Prevent stale async results from corrupting state after reset or reconfiguration
globs: uar/**/*.py
tags: [python, concurrency, threading, state-machine, race-condition]
---

# Backend Generation Guard for Async State Machines

## Rule

Any stateful object that allows external `reset()` or reconfiguration while async operations may be in-flight **must** use a monotonic generation counter to invalidate stale completions.

## Why

Without a generation counter, an async call that started before `reset()` can complete afterward and overwrite the freshly-reset state. In circuit breakers, this means a stale failure re-opens a breaker the operator just reset. In connection pools, it means a stale timeout poisons a newly-healthy endpoint.

## Bad

```python
class CircuitBreaker:
    def reset(self):
        with self._lock:
            self._state = State.CLOSED
            self._failures = 0

    async def call_async(self, fn, *args, **kwargs):
        with self._lock:
            self._transition()
            if self._state == State.OPEN:
                raise CircuitBreakerOpenError(self.name)
            reserved = True

        try:
            result = await fn(*args, **kwargs)
        except Exception:
            with self._lock:
                self._failures += 1
                if self._failures >= self.threshold:
                    self._state = State.OPEN   # BUG: can reopen after reset
            raise
```

## Good

```python
class CircuitBreaker:
    def __init__(self):
        self._generation = 0

    def reset(self):
        with self._lock:
            self._generation += 1
            self._state = State.CLOSED
            self._failures = 0

    async def call_async(self, fn, *args, **kwargs):
        with self._lock:
            self._transition()
            if self._state == State.OPEN:
                raise CircuitBreakerOpenError(self.name)
            reserved = True
            _gen = self._generation

        try:
            result = await fn(*args, **kwargs)
        except Exception:
            with self._lock:
                if self._generation == _gen:
                    self._failures += 1
                    if self._failures >= self.threshold:
                        self._state = State.OPEN
            raise

        with self._lock:
            if self._generation != _gen:
                return result   # stale success, ignore state updates
            self._failures = 0
            # ... success path state updates
```

## Key Points

1. **Capture generation inside the reservation lock** — before executing outside the lock.
2. **Check generation before every post-execution state update** — both success and failure paths.
3. **Still re-raise exceptions** — generation guard skips state mutation, but the caller must still see the exception.
4. **Increment on reset** — any operation that invalidates in-flight work must bump the counter.

## Applies To

- Circuit breakers, bulkheads, rate limiters with manual reset
- Connection pools with endpoint reconfiguration
- Any state machine with external reset and async execution
