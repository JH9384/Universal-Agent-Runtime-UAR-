---
description: Prevent setTimeout/setInterval leaks in React components
tags: [react, hooks, memory-leak, frontend]
---

# Rule: Clean Up setTimeout / setInterval in React Components

## Problem

`setTimeout` or `setInterval` callbacks that call `setState` after a component unmounts cause React memory-leak warnings and may corrupt state in sibling components that reuse the same state slot.

## Detection

Any `setTimeout` or `setInterval` inside a React component that:

1. Calls `setState` (or any React state setter) in its callback, **and**
2. Is not cleared in a `useEffect` cleanup or `useCallback`/`useRef` teardown

## Prevention

### For event-handler timers (e.g. copy flash, auto-dismiss)

Store the handle in a `useRef` and clear it both before starting a new one and in a mount/unmount `useEffect` cleanup.

**Bad:**

```tsx
function copyId(id: string) {
  navigator.clipboard.writeText(id).then(() => {
    setCopied(id);
    setTimeout(() => setCopied(null), 1500);  // leaks on unmount
  });
}
```

**Good:**

```tsx
const copyTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

useEffect(() => {
  return () => {
    if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
  };
}, []);

function copyId(id: string) {
  if (copyTimerRef.current) clearTimeout(copyTimerRef.current);
  navigator.clipboard.writeText(id).then(() => {
    setCopied(id);
    copyTimerRef.current = setTimeout(() => {
      setCopied(null);
      copyTimerRef.current = null;
    }, 1500);
  });
}
```

### For polling intervals inside useEffect

Always return a cleanup function that clears the interval.

**Bad:**

```tsx
useEffect(() => {
  const id = setInterval(fetchData, 10_000);
}, []);  // interval leaks forever
```

**Good:**

```tsx
useEffect(() => {
  const id = setInterval(fetchData, 10_000);
  return () => clearInterval(id);
}, []);
```

## Checklist

- [ ] Every `setTimeout` that calls `setState` has a corresponding `clearTimeout`
- [ ] Timer handles are stored in `useRef` (not local variables) when they must outlive the function that created them
- [ ] `useEffect` with timers always returns a cleanup function
- [ ] Before starting a new timer of the same kind, clear any existing one (prevents duplicate timers from rapid user clicks)
