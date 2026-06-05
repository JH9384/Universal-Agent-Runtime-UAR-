---
description: Prevent double-clicks and poll-blocking on frontend mutation handlers (POST/PUT/DELETE/reset)
globs: apps/**/src/**/*.tsx
tags: [react, frontend, async, fetch, mutation, ux]
---

# Frontend Mutation In-Flight Guard

## Rule

Every user-triggered mutation handler (POST, PUT, DELETE, reset, submit) **must** use an **independent** in-flight guard, separate from polling/refetch guards.

## Why

Reusing a single `inFlightRef` for both reads (polls) and writes (mutations) causes two distinct bugs:

1. **Double-clicks fire parallel requests** — React state-based `disabled` is asynchronous. The browser can deliver a second `onClick` before React re-renders and disables the button.
2. **Mutations silently dropped during polls** — If a poll is in-flight when the user clicks a mutation button, the handler returns early with no feedback. The user sees an enabled button and a click that does nothing.

## Bad

```tsx
const inFlightRef = useRef(false);

const load = useCallback(async (signal?: AbortSignal) => {
  if (inFlightRef.current) return;
  inFlightRef.current = true;
  // ... fetch
  inFlightRef.current = false;
}, []);

function handleReset(name: string) {
  if (inFlightRef.current) return;   // BUG: blocked during poll, no feedback
  setResetting(name);
  api.resetCircuitBreaker(name)       // BUG: no signal, no mounted guard on .then()
    .then(() => load())
    .catch((err) => setError(String(err)))
    .finally(() => setResetting(null));
}
```

## Good

```tsx
const inFlightRef = useRef(false);
const resetInFlightRef = useRef(false);

function handleReset(name: string) {
  if (resetInFlightRef.current) return;
  resetInFlightRef.current = true;
  setResetting(name);

  const signal = abortCtrlRef.current?.signal;
  api
    .resetCircuitBreaker(name, signal ? { signal } : undefined)
    .then(() => {
      if (!mountedRef.current) return;
      load(signal);
    })
    .catch((err) => {
      if ((err as Error)?.name === "AbortError") return;
      if (mountedRef.current) setError(String(err));
    })
    .finally(() => {
      resetInFlightRef.current = false;
      if (mountedRef.current) {
        setResetting((prev) => (prev === name ? null : prev));
      }
    });
}
```

## Checklist

- [ ] Mutation handlers have their own `*InFlightRef`, not shared with read operations
- [ ] In-flight flag is set **before** the API call, not after `setState`
- [ ] In-flight flag is cleared in `.finally()`, not just `.then()`
- [ ] `AbortSignal` from the component's `AbortController` is passed to the mutation API call
- [ ] `.then()` and `.catch()` callbacks check `mountedRef.current` before state updates
- [ ] `AbortError` is explicitly filtered in `.catch()` and not surfaced to the user
