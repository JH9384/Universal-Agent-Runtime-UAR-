---
description: Frontend streaming, SSE, and async error-handling rules for UAR React/Svelte apps
---

# Frontend Streaming & Async Error-Handling Rules

## 1. AbortController is mandatory for every fetch/stream

- Every `fetch()` that can outlive a component must accept or create an `AbortController`.
- Pass `signal` to `fetch()` and abort it in cleanup (`useEffect` return / `onDestroy`).
- **Bad:** `await fetch(url, { method: 'POST', body })`
- **Good:** `const ctrl = new AbortController(); await fetch(url, { signal: ctrl.signal, ... }); onDestroy(() => ctrl.abort())`

## 2. Unhandled promise rejections are forbidden

- Every async function called from user interaction or lifecycle must have a `catch` or `try/catch`.
- Promise chains must not end in `.then().finally()` without `.catch()`.
- **Bad:** `api.resetCircuitBreaker(name).then(() => load()).finally(() => setResetting(null))`
- **Good:** `api.resetCircuitBreaker(name).then(() => load()).catch(setError).finally(() => setResetting(null))`

## 3. SSE parser must handle \r\n and multi-line data

- Split buffer on `/\n\n|\r\n\r\n/`, not literal `'\n\n'`.
- Split lines inside each chunk on `/\r?\n/`, not literal `'\n'`.
- Strip `data:` prefix with `/^data:\s?/`, not `replace('data: ', '')` (fragile if data contains that substring).
- Concatenate multiple `data:` lines with `'\n'` before `JSON.parse`.

## 4. ReadableStream readers must be cancelled before releaseLock

- In `finally`: `await reader.cancel(); reader.releaseLock();`
- **Bad:** `try { reader.releaseLock() } catch {}`
- **Good:** `try { await reader.cancel(); } catch {} try { reader.releaseLock(); } catch {}`

## 5. Accumulating arrays must have a hard cap

- Any event log, message buffer, or run history must declare `const MAX_EVENTS = N` and enforce it.
- **Bad:** `events = [...events, ev]` (unbounded)
- **Good:** `events = [...events, ev]; if (events.length > MAX_EVENTS) events = events.slice(-MAX_EVENTS)`

## 6. O(n²) reactive computations are forbidden

- Do not copy + reverse an array on every reactive update.
- Prefer CSS `flex-direction: column-reverse` or prepend items instead.
- **Bad:** `$: reversed = [...events].reverse()` (O(n) per event)
- **Good:** `<div style="display: flex; flex-direction: column-reverse;">` or maintain reverse order natively

## 7. onError callbacks must actually be invoked

- If a service method accepts `onError`, every error path must call it.
- Parse errors, network errors, HTTP errors, and reader exceptions all must surface through `onError`.
- **Bad:** `catch { /* skip malformed */ }`
- **Good:** `catch (err) { onError?.('Malformed event: ' + String(err)) }`

## 8. Cleanup is mandatory for all subscriptions, intervals, and listeners

- `setInterval` / `setTimeout` → clear in cleanup.
- `addEventListener` → remove in cleanup.
- `WebSocket` → close in cleanup.
- For React: use `useRef` for `mounted` flag when the flag is needed outside `useEffect` (e.g., in click handlers).
