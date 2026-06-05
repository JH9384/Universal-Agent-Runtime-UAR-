---
description: Prevent overlapping async requests, interval drift, and request leaks in React polling components
tags: [react, hooks, polling, frontend, async, fetch]
---

# Rule: Safe Async Polling in React Components

## Problem

Using naive polling in React creates **four** distinct failure modes:

1. **Overlapping requests** — If an API call takes longer than the interval, a second request fires while the first is still in-flight. Responses can resolve out of order, causing stale data to overwrite fresh data.
2. **Request leaks on unmount** — A `mounted` flag prevents state updates after unmount, but the underlying `fetch()` transaction continues to the network layer unnecessarily.
3. **Stale closure capture** — Functions defined inside `useEffect` with empty deps capture the initial closure forever. If they reference mutable refs, that is safe; if they ever reference non-stable values, they operate on stale data.
4. **Interval drift** — Scheduling the next tick *after* the current request completes (`setTimeout` inside `.finally()`) means the actual interval becomes `request_latency + intended_interval`, which drifts unpredictably with backend variance.
5. **Uninitialized timer handles** — Declaring `let timeoutId: ReturnType<typeof setTimeout>` without an initial value causes `clearTimeout(undefined)` on early unmount. This is brittle and can fail under strict TypeScript null checks.

## Detection

Any React component that:

1. Uses `setInterval` to schedule recurring async network requests without an `inFlight` guard, **or**
2. Polls data in `useEffect` without an `AbortController` to cancel in-flight requests on unmount, **or**
3. Schedules the next poll inside `.finally()` or `.then()` of the async request, **or**
4. Declares a timer handle without initializing it to `undefined`

## Prevention

### Use `setInterval` with an `inFlight` guard for fixed cadence

`setInterval` keeps a fixed cadence. Pair it with an `inFlight` flag to skip ticks when the previous request is still running, preventing overlap while preserving timing.

**Bad (overlapping requests):**

```tsx
useEffect(() => {
  const fetchData = async () => { /* ... */ };
  fetchData();
  const id = setInterval(fetchData, 5000); // fires even if fetchData is still running
  return () => clearInterval(id);
}, []);
```

**Bad (interval drift):**

```tsx
useEffect(() => {
  let timeoutId: ReturnType<typeof setTimeout>; // uninitialized — brittle on early unmount
  const abortCtrl = new AbortController();

  function tick() {
    fetchData(abortCtrl.signal).finally(() => {
      if (mountedRef.current) {
        timeoutId = setTimeout(tick, 5000); // interval drifts by request latency
      }
    });
  }

  tick();
  return () => {
    mountedRef.current = false;
    abortCtrl.abort();
    clearTimeout(timeoutId);
  };
}, []);
```

**Good:**

```tsx
useEffect(() => {
  let timeoutId: ReturnType<typeof setTimeout> | undefined;
  let inFlight = false;
  const abortCtrl = new AbortController();

  function tick() {
    if (inFlight) return;           // skip tick if previous request still running
    inFlight = true;
    fetchData(abortCtrl.signal).finally(() => {
      inFlight = false;
      if (mountedRef.current) setLoading(false);
    });
  }

  tick();
  timeoutId = setInterval(tick, 5000); // fixed 5-second cadence, no drift
  return () => {
    mountedRef.current = false;
    abortCtrl.abort();
    clearInterval(timeoutId);
  };
}, []);
```

### Forward `AbortSignal` through your API layer

Ensure your API client methods accept and forward an `AbortSignal` to `fetch`.

**Bad:**

```ts
export const api = {
  circuitBreakers(): Promise<CircuitBreakerStates> {
    return fetchJson("/api/health/circuit-breakers"); // no way to cancel
  },
};
```

**Good:**

```ts
export const api = {
  circuitBreakers(init?: RequestInit): Promise<CircuitBreakerStates> {
    return fetchJson("/api/health/circuit-breakers", init);
  },
};
```

`fetchJson` should spread `init` (which carries `signal`) into the `fetch` call:

```ts
const response = await fetch(url, {
  ...init,
  headers: { "Content-Type": "application/json", ...authHeader, ...extraHeaders },
});
```

### Deduplicate overlapping refreshes with a request-generation ref

When manual refreshes (e.g., user clicks "Reset") can race with polling ticks, track a monotonic generation counter:

```tsx
const reqGenRef = useRef(0);

async function load(signal?: AbortSignal) {
  const myGen = ++reqGenRef.current;
  const data = await api.circuitBreakers({ signal });
  if (reqGenRef.current !== myGen) return; // stale response, discard
  setData(data);
}
```

This prevents a slow poll response from overwriting data set by a faster manual refresh.

## Checklist

- [ ] Timer handles are declared with `| undefined` (e.g. `let timeoutId: ReturnType<typeof setTimeout> | undefined`)
- [ ] Polling uses `setInterval` with an `inFlight` guard, NOT recursive `setTimeout` inside `.finally()` / `.then()`
- [ ] Every polling `useEffect` creates an `AbortController` and aborts it in cleanup
- [ ] API client methods accept an optional `RequestInit` (or `signal`) parameter
- [ ] Cleanup function clears both the interval AND aborts in-flight requests
- [ ] Manual refreshes and polling ticks are deduplicated if they can race (use generation counter or AbortController)
