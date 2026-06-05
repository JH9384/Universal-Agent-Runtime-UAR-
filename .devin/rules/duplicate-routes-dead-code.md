---
description: Prevent duplicate FastAPI routes and frontend dead code
tags: [fastapi, routes, frontend, dead-code]
---

# Rule: No Duplicate FastAPI Routes

## Problem
FastAPI silently resolves duplicate `@router.*` decorators to the **first** registered handler. The second handler becomes unreachable dead code, and any bug fixes applied to it silently have no effect.

## Detection
Run this command before committing router changes:
```bash
rg '@router\.(get|post|put|delete|patch)\("[^"]+"' uar/api/routers -g '*.py' -o | sort | uniq -d
```
Any output means duplicate routes exist.

## Prevention
1. Each route path must appear in exactly one router file.
2. If a route needs to move, delete it from the source file before adding to the destination.
3. Router registration order in `uar/boot.py` and `uar/api/routers/__init__.py` matters — the first registered wins.

## Example of what NOT to do
```python
# topology.py
@router.get("/api/uar/topology/hot-paths")
async def topology_hot_paths(...): ...

# runs.py
@router.get("/api/uar/topology/hot-paths")
async def get_topology_hot_paths(...): ...
```

---

# Rule: Match Function Call Arity to Signature

## Problem
When a function signature gains required positional arguments, all callers must be updated. Python static analysis will not catch this until runtime.

## Detection
Before committing changes to functions with many callers (e.g. `build_analytics_snapshot`), grep for all call sites and verify argument count matches.

## Prevention
1. Prefer functions with explicit keyword arguments over long positional arg lists.
2. When adding required args, update ALL call sites in the same commit.
3. Add type stubs if possible.

## Example of what NOT to do
```python
# Function now requires 5 args
def build_analytics_snapshot(runs, user, is_admin, hours, limit): ...

# Caller still passes 1 arg — crashes at runtime
snapshot = build_analytics_snapshot(runs)
```

---

# Rule: No Unused Computed Values in Frontend

## Problem
`useMemo`, `useCallback`, `$:` (Svelte reactive) and similar computed values cost CPU/memory. Declaring them without using the result wastes resources and confuses readers.

## Detection
1. For React: search for `const X = useMemo(...)` or `const X = useCallback(...)` where `X` is referenced 0 or 1 times (only the declaration).
2. For Svelte: search for `$: X = ...` where `X` is never referenced outside its declaration.

## Prevention
1. Remove `useMemo`/`useCallback` wrappers if the result is unused.
2. Remove helper components (e.g. `RateBar`) if they are never rendered.
3. Run dead-code elimination tools or linters (ESLint `react-hooks/exhaustive-deps`, `no-unused-vars`).

## Example of what NOT to do
```tsx
const maxInvocations = useMemo(() => Math.max(...), [data]) // never read
const maxTransitions = useMemo(() => Math.max(...), [data]) // never read

function RateBar() { ... } // defined but never used in JSX
```

---

# Rule: Use Accepted Query Parameters

## Problem
Endpoint handlers that declare `Query(...)` parameters but never reference them in the body are misleading to API consumers. The parameter appears in docs but has no effect.

## Detection
For each `Query(...)` parameter in a router function, verify the parameter name appears in the function body (or is passed to a helper).

## Prevention
1. If a parameter is intentionally ignored, document why (e.g. `# reserved for future use`).
2. Otherwise remove the unused parameter.

## Example of what NOT to do
```python
@router.get("/api/uar/topology/hot-paths")
async def hot_paths(
    hours: int = Query(168, ...),  # declared
    top: int = Query(20, ...),
):
    runs = store.list_records(limit=50000)  # hours never used
```
