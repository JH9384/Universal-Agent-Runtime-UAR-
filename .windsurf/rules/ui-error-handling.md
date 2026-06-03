---
description: UI error handling, auto-dismiss, and accessibility rules
---

# UI Error Handling

## No Auto-Dismiss

Errors must **never** auto-dismiss with a timer. Users may miss critical
failures. Provide an explicit **Dismiss** button only.

```tsx
// BAD — error vanishes after 8s
useEffect(() => {
  if (!error) return
  const id = setTimeout(() => setError(null), 8000)
  return () => clearTimeout(id)
}, [error])

// GOOD — persistent until dismissed
<button onClick={() => setError(null)}>Dismiss</button>
```

## Parse Errors Don't Overwrite Real Errors

Recoverable parse errors (malformed SSE chunk, WebSocket message) should be
logged to console only. Never overwrite the actual `error` state that may
contain a user-facing server error.

```tsx
// BAD
} catch (parseError) {
  setError({ message: 'Failed to parse server response' })
}

// GOOD
} catch (parseError) {
  console.error('Parse error on SSE chunk:', parseError, line)
}
```

## aria-live="assertive" Is Dangerous

`aria-live="assertive"` interrupts screen readers on every re-render of the
element, not just when the content changes. Use `"polite"` instead, or manage
announcements with a dedicated live region that only updates on state change.

```tsx
// BAD — interrupts on every render
<div role="alert" aria-live="assertive">{error.message}</div>

// GOOD — queues announcement
<div role="alert" aria-live="polite">{error.message}</div>
```

## localStorage Failures Must Be Visible

When `localStorage` quota is exceeded, a console log is invisible to users.
Surface it as a visible error banner with a recovery action.

```tsx
// BAD
console.error('localStorage quota exceeded')

// GOOD
setError({
  message: 'Storage full: changes not persisted. Export your data.',
  code: 'STORAGE_QUOTA',
})
```

## Progress Feedback for Long Operations

Operations that may take >30s must show elapsed time and progress indicators
(event count, percentage, steps completed).

```tsx
<span>
  {currentSkill} • {Math.floor(elapsedMs / 1000)}s • {eventCount} events
</span>
```

## Destructive Actions Require Confirmation

Any irreversible action (delete file, clear history, remove recipe) must have
an explicit confirmation step.

```tsx
const handleDelete = (name: string) => {
  if (!confirm(`Delete "${name}"? This cannot be undone.`)) return
  // proceed...
}
```
