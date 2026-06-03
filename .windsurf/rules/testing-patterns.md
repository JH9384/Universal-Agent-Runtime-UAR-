---
description: Testing patterns for frontend (Vitest/React Testing Library) and backend (pytest) regression suites
globs: [apps/operator-dashboard/src/**/*.test.tsx, tests/**/*.py]
---

# Testing Patterns

## Frontend (Operator Dashboard)

### 1. Mock Cleanup

Every test file MUST clear mocks between tests to prevent cross-test pollution:

```ts
import { vi, afterEach } from 'vitest'

afterEach(() => vi.clearAllMocks())
```

Or per-suite in `beforeEach` when using `vi.mock` at module level.

### 2. Unmount Guard Tests

Any component that calls `setState` after an async operation MUST have a test verifying it does not update after unmount:

```ts
it('does not set state after unmount', async () => {
  let resolvePromise: (value: unknown) => void = () => {}
  vi.mocked(api.someEndpoint).mockImplementation(
    () => new Promise((resolve) => { resolvePromise = resolve })
  )

  const { unmount } = render(<MyComponent />)
  unmount()
  resolvePromise({ data: 'value' })

  // Passes silently if mountedRef guard is present; React warns otherwise
})
```

### 3. ARIA Attribute String Tests

ARIA attributes MUST be strings (`"true"` / `"false"`), not booleans:

```ts
it('aria-selected is string, not boolean', () => {
  render(<App />)
  const tab = screen.getByRole('tab', { name: /Health/i })
  const val = tab.getAttribute('aria-selected')
  expect(['true', 'false']).toContain(val)
})
```

Apply to: `aria-selected`, `aria-pressed`, `aria-expanded`, `aria-hidden`.

### 4. React Key Prop Tests

Conditional empty-state list items inside `<ul>` MUST carry a stable `key` prop:

```ts
function assertNoKeyWarning(renderFn: () => unknown): unknown {
  const spy = vi.spyOn(console, 'error').mockImplementation(() => {})
  try {
    const result = renderFn()
    const keyCalls = spy.mock.calls.filter((call) =>
      call.some((arg) => typeof arg === 'string' && /Each child in a list should have a unique "key" prop/.test(arg))
    )
    expect(keyCalls).toHaveLength(0)
    return result
  } finally {
    spy.mockRestore()
  }
}

it('no key warning when list is empty', () => {
  vi.mocked(api.listItems).mockResolvedValue([])
  assertNoKeyWarning(() => render(<MyList />))
})
```

### 5. CSS Class Regression Tests

Any CSS class used for styling or state indication MUST have a regression test:

```ts
it('uses warning class when degraded', async () => {
  vi.mocked(api.status).mockResolvedValue({ degraded: true })
  render(<StatusPanel />)
  await waitFor(() => screen.getByText('Degraded'))
  expect(screen.getByText('Degraded').className).toContain('mc-status--warn')
})
```

### 6. Error Boundary / Rejection Tests

Async operations with `.catch()` MUST be tested for graceful rejection:

```ts
it('does not throw when clipboard.writeText rejects', async () => {
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: vi.fn().mockRejectedValue(new Error('denied')) },
    writable: true,
    configurable: true,
  })
  render(<Component />)
  await waitFor(() => screen.getByTitle('Copy'))
  expect(() => fireEvent.click(screen.getByTitle('Copy'))).not.toThrow()
})
```

## Backend (Python / pytest)

### 1. Source Inspection Tests

When a fix depends on implementation order or specific code patterns, use `inspect.getsource` to assert the fix is present:

```python
import inspect

def test_foo_acquires_lock_before_mutating():
    src = inspect.getsource(module._some_function)
    assert "with _lock:" in src, (
        "_some_function must acquire _lock before mutating shared state"
    )
```

Apply to: lock ordering, variable initialization before function defs, exception handler ordering.

### 2. Thread-Safety Tests

Any shared mutable state MUST be tested under concurrency:

```python
def test_shared_cache_is_thread_safe():
    results: list = []

    def _worker():
        for _ in range(100):
            results.append(get_cached_value("key"))

    threads = [threading.Thread(target=_worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert all(r == expected for r in results), "Cache corruption detected"
```

### 2b. Reservation vs Completion Counter Bug

When a counter tracks slots reserved under a lock but is checked at completion time, the counter measures reservations, not completions. This causes premature state transitions when concurrent requests are in flight.

**Anti-pattern (bug):**

```python
with lock:
    if state == HALF_OPEN:
        half_open_count += 1          # reservation
try:
    result = fn()
finally:
    with lock:
        if half_open_count >= max:    # BUG: uses reservation count
            state = CLOSED
```

**Correct pattern:**

```python
with lock:
    if state == HALF_OPEN:
        half_open_count += 1          # reservation counter
try:
    result = fn()
finally:
    with lock:
        if state == HALF_OPEN:
            half_open_successes += 1  # separate completion counter
            if half_open_successes >= max:
                state = CLOSED
```

**Required regression test:** Verify that when `max > 1` and all slots are reserved concurrently, the circuit stays in the intermediate state until each call individually completes successfully:

```python
def test_half_open_uses_success_counter_not_reservation_count():
    breaker = CircuitBreaker(
        "test", failure_threshold=2, recovery_timeout=0.1, half_open_max=3
    )
    # Open circuit, wait for timeout → HALF_OPEN
    # Start 3 slow calls concurrently, each reserves a slot
    # Complete them one by one; circuit should stay HALF_OPEN until the 3rd success
```

### 2c. BaseException Counter Leak

`except Exception:` does NOT catch `asyncio.CancelledError`, `KeyboardInterrupt`, or `GeneratorExit`. If a protected block reserves a slot/counter under a lock and only decrements it in `except Exception:`, those base exceptions cause a permanent resource leak.

**Anti-pattern (bug):**

```python
try:
    result = await fn()
except Exception:
    with lock:
        pending -= 1
    raise
```

**Correct pattern:**

```python
try:
    result = await fn()
except BaseException as exc:
    with lock:
        pending -= 1
        if isinstance(exc, Exception):
            failures += 1
    raise
```

**Required regression test:** Cancel a task wrapped by a circuit breaker and assert counters return to zero:

```python
def test_cancelled_error_decrements_pending_calls():
    async def _test():
        task = asyncio.create_task(cb.call_async(slow))
        await asyncio.sleep(0.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert cb._pending_calls == 0
        assert cb._failures == 0
    asyncio.run(_test())
```

### 3. Mock-Based DB Tests (No Real Network)

Tests for DB stores MUST mock connections/pools to avoid real network calls:

```python
def test_append_writes_correct_fields(monkeypatch):
    captured = {}

    class MockConn:
        def cursor(self):
            return MockCur()

    class MockCur:
        def execute(self, sql, data):
            captured.update(data)

    class MockPool:
        def getconn(self): return MockConn()
        def putconn(self, conn): pass

    store = PostgresRunStore.__new__(PostgresRunStore)
    store._pool = MockPool()
    monkeypatch.setattr(store, "_ensure_table", lambda: None)

    store.append(FakeRecord(run_id="r1"))
    assert captured["run_id"] == "r1"
```

### 4. Environment Isolation

Tests that modify `os.environ` MUST restore the original value in a `finally` block:

```python
def test_behavior_with_overflow_enabled():
    old_env = os.environ.get("UAR_CONTEXT_DISK_OVERFLOW")
    os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = "true"
    try:
        # ... test code ...
    finally:
        if old_env is None:
            os.environ.pop("UAR_CONTEXT_DISK_OVERFLOW", None)
        else:
            os.environ["UAR_CONTEXT_DISK_OVERFLOW"] = old_env
```

### 5. Idempotency Tests

Cleanup/close methods MUST be callable multiple times without error:

```python
def test_close_is_idempotent():
    ctx = PipelineContext(goal=goal)
    ctx.close()
    ctx.close()  # Should not raise
```

## Checklist for New Tests

- [ ] Frontend: `vi.clearAllMocks()` in `afterEach` or `beforeEach`
- [ ] Frontend: Unmount guard tested for async components
- [ ] Frontend: ARIA boolean attributes tested as strings
- [ ] Frontend: Empty-state conditional list items have key prop tests
- [ ] Frontend: CSS classes tested for state-dependent styling
- [ ] Frontend: Async rejections handled gracefully
- [ ] Backend: Source inspection for ordering-dependent fixes
- [ ] Backend: Thread-safety for shared mutable state
- [ ] Backend: DB mocks used instead of real connections
- [ ] Backend: Environment variables restored after test
- [ ] Backend: Idempotency for cleanup/close operations
