# UAR Code Patterns — Rules for Cascade

## Frontend (React/TS)

### Rule FE-1: Live Dashboard Panels Must Poll
Any component embedded in a live dashboard (Mission Control, operator panels, etc.) that fetches dynamic data via `useApiFetch` MUST pass `{ interval: 30_000 }` (or appropriate interval). Single-fetch is only acceptable for user-triggered or detail views.

**Bad:**
```tsx
const { data } = useApiFetch<HealthData>('/api/uar/health')
```

**Good:**
```tsx
const { data } = useApiFetch<HealthData>('/api/uar/health', { interval: 30_000 })
```

### Rule FE-2: Mutation Feedback Must Refetch
After a successful mutation POST (feedback, actions, etc.), the component MUST refetch the affected dataset so the UI reflects the new state. Pass the `refetch` callback from `useApiFetch` to the mutation handler.

**Bad:**
```tsx
const { data } = useApiFetch<Data>('/api/uar/items')
// on click: POST /api/uar/items/action — UI stays stale
```

**Good:**
```tsx
const { data, refetch } = useApiFetch<Data>('/api/uar/items', { interval: 30_000 })
// on click: POST then onSuccess?.() to trigger refetch
```

### Rule FE-3: Guard setState After Async Cleanup
Any promise chain (`fetch`, `api.*`, event callbacks) that calls `setState` in `.then()`, `.catch()`, or `.finally()` MUST check a `mounted` / `mountedRef` guard before every state update. React warns and may leak if state is set after unmount.

**Bad:**
```tsx
useEffect(() => {
  api.healthDashboard()
    .then((d) => setHealth(d))   // unmount → warning
    .finally(() => setLoading(false)); // unmount → warning
}, []);
```

**Good:**
```tsx
useEffect(() => {
  let mounted = true;
  api.healthDashboard()
    .then((d) => { if (mounted) setHealth(d); })
    .finally(() => { if (mounted) setLoading(false); });
  return () => { mounted = false; };
}, []);
```

### Rule FE-4: Normalize Headers Before Spreading
When merging `init?.headers` into a plain object via spread (`...`), always normalize a `Headers` instance first. `Headers` has no enumerable own properties, so `...(new Headers())` silently drops all values.

**Bad:**
```tsx
headers: { 'Content-Type': 'application/json', ...(init?.headers as Record<string, string> ?? {}) }
```

**Good:**
```tsx
const extraHeaders: Record<string, string> =
  init?.headers instanceof Headers
    ? Object.fromEntries(init.headers.entries())
    : (init?.headers as Record<string, string> ?? {});
headers: { 'Content-Type': 'application/json', ...extraHeaders }
```

### Rule FE-5: Nested Ternary Precedence — Order by Severity
In a chain of nested ternaries that compute a mode/state from multiple booleans, list conditions in descending severity order. A less-severe condition must never mask a more-severe one.

**Bad:**
```tsx
const mode = openCount > 0 ? "degraded" : halfOpenCount > 0 ? "recovering" : starvation ? "starved" : "healthy";
// If halfOpenCount>0 AND starvation, mode is "recovering" — starvation is masked.
```

**Good:**
```tsx
const mode = openCount > 0 ? "degraded" : starvation ? "starved" : halfOpenCount > 0 ? "recovering" : "healthy";
```

## Backend (Python)

### Rule BE-1: Per-Item try/except in Mutation Loops
When iterating over a collection and mutating each item, wrap the PER-ITEM body in `try/except`, not the entire loop. A single failure must not leave the batch in a partially-corrupted state.

**Bad:**
```python
try:
    for rec in recommendations:
        rec.confidence = rec.confidence * modifier  # if this fails on item 5, items 1-4 are mutated
except Exception:
    pass
```

**Good:**
```python
for rec in recommendations:
    try:
        rec.confidence = rec.confidence * modifier
    except Exception:
        logger.exception("Failed for %s", rec.id)
```

### Rule BE-2: Invalidate Cache on Mutation
Any endpoint that mutates data consumed by a cached analytics endpoint MUST invalidate the relevant cache key after persistence. Default to invalidating the specific endpoint; use `invalidate()` (all) only when the change truly affects every cached view.

**Bad:**
```python
store.record_feedback(rec_id, action)
return {"ok": True}
# Next GET /recommendations still serves stale cache
```

**Good:**
```python
store.record_feedback(rec_id, action)
_analytics_cache().invalidate("recommendations-v2")
return {"ok": True}
```

### Rule BE-3: Dict Existence Check Must Use `is not None`
When a function returns `dict | None`, check `if result is not None:` rather than `if result:`. An empty dict `{}` is a valid success result but evaluates falsy.

**Bad:**
```python
trust_result = compute_trust(...)
if trust_result:  # skips when trust_result == {}
    ...
```

**Good:**
```python
trust_result = compute_trust(...)
if trust_result is not None:
    ...
```

### Rule BE-4: Don't Truncate Multi-Value Data
When a field conceptually holds multiple values (e.g., `affected_runs`), persist all values rather than silently taking only the first element. Use comma-join, JSON arrays, or schema changes — never drop data.

**Bad:**
```python
run_id=rec.affected_runs[0] if rec.affected_runs else ""
```

**Good:**
```python
run_id=",".join(rec.affected_runs) if rec.affected_runs else ""
```

### Rule BE-5: JSON-Derived Booleans Must Not Use Identity Comparison
Values deserialized from JSON (`.get()`, `json.loads`, HTTP bodies) may be `0`, `1`, numpy booleans, or plain Python booleans. `is False` and `is True` are identity checks that fail on truthy/falsy equivalents. Use `is not None and not val` / `is not None and val` instead.

**Bad:**
```python
burnin_passed = cert.get("evidence", {}).get("burnin_passed")
if burnin_passed is False:  # fails when upstream sends 0 or numpy bool
    ...
```

**Good:**
```python
burnin_passed = cert.get("evidence", {}).get("burnin_passed")
if burnin_passed is not None and not burnin_passed:
    ...
```

### Rule BE-7: Admin Visibility Must Use `None if is_admin else user`
When fetching records for analytics endpoints that support both regular users and admins, the `user_id` filter MUST be `None if is_admin else user` so admins see all records. `user if is_admin else user` is a tautology that silently breaks admin visibility.

**Bad:**
```python
all_runs = store.list_records(
    user_id=user if is_admin else user, limit=limit
)
```

**Good:**
```python
all_runs = store.list_records(
    user_id=None if is_admin else user, limit=limit
)
```

### Rule BE-9: Static Routes Must Precede Dynamic Path Parameters
In FastAPI, routes are matched in definition order. A static route like `/items/summary` defined AFTER `/{item_id}` will never match because `summary` is treated as an `item_id`. Always define static routes before dynamic ones, or add a programmatic reordering block at module load time.

**Bad:**
```python
@router.get("/api/uar/runs/{run_id}")
async def get_run(run_id: str): ...

@router.get("/api/uar/runs/failure-clusters")  # Never reached
async def get_failure_clusters(): ...
```

**Good:**
```python
@router.get("/api/uar/runs/failure-clusters")
async def get_failure_clusters(): ...

@router.get("/api/uar/runs/{run_id}")
async def get_run(run_id: str): ...
```

Or, when refactoring is impractical, add a reordering block:
```python
_STATIC_FIRST_PATHS = {"/api/uar/runs/failure-clusters"}
for _path in _STATIC_FIRST_PATHS:
    _static_idx = next((i for i, r in enumerate(router.routes)
                       if getattr(r, "path", None) == _path), None)
    _dynamic_idx = next((i for i, r in enumerate(router.routes)
                        if getattr(r, "path", None) == "/api/uar/runs/{run_id}"), None)
    if _static_idx is not None and _dynamic_idx is not None \
            and _static_idx > _dynamic_idx:
        router.routes.insert(_dynamic_idx, router.routes.pop(_static_idx))
```

### Rule BE-8: FastAPI `Request` Must Precede Default Parameters
In FastAPI endpoint signatures, `request: Request` (which has no default) MUST appear before parameters with defaults like `Query(...)`. Python syntax forbids non-default arguments following default arguments. FastAPI injects `Request` regardless of position, but the interpreter enforces declaration order.

**Bad:**
```python
async def get_failure_clusters(
    hours: int = Query(24, ge=1, le=168),
    request: Request,  # SyntaxError: non-default argument follows default argument
    ...
):
```

**Good:**
```python
async def get_failure_clusters(
    request: Request,
    hours: int = Query(24, ge=1, le=168),
    ...
):
```

### Rule BE-6: Don't Emit Duplicate Alerts for the Same Root Cause
When multiple conditions stem from the same subsystem (e.g., certification both "degraded" and score < 50), aggregate them into a single alert. Duplicate alerts waste the limited payload budget and dilute operator attention.

**Bad:**
```python
if "degraded" in cert_level:
    alerts.append({"level": "critical", "source": "certification", ...})
if cert_score < 50:
    alerts.append({"level": "critical", "source": "certification", ...})
```

**Good:**
```python
cert_issues = []
if "degraded" in cert_level:
    cert_issues.append("degraded")
if cert_score is not None and cert_score < 50:
    cert_issues.append("score collapsed")
if cert_issues:
    alerts.append({"level": "critical", "source": "certification",
                   "message": f"Certification {'; '.join(cert_issues)}"})
```

## Frontend (React/TS) — continued

### Rule FE-6: Alert/Status Banners Must Have ARIA Roles
Any component that visually signals alerts, warnings, or critical system state MUST include `role="alert"` (for urgent conditions) or `role="status"` (for non-urgent state changes). Decorative icons inside MUST have `aria-hidden="true"`.

**Bad:**
```tsx
<div className={styles.banner}>
  <span>{LEVEL_ICON[top.level]}</span>
  <span>{top.message}</span>
</div>
```

**Good:**
```tsx
<div className={styles.banner} role="alert">
  <span aria-hidden="true">{LEVEL_ICON[top.level]}</span>
  <span>{top.message}</span>
</div>
```

### Rule FE-7: Count Badges Must Reference the Visible Payload
When a backend truncates a list (e.g., `alerts[:5]`) but returns a total `count`, the frontend badge MUST reference the length of the actually-renderable array, not the backend total. Showing "+19" when only 4 more alerts are in the payload is misleading.

**Bad:**
```tsx
{data.count > 1 && (
  <span className={styles.count}>+{data.count - 1}</span>
)}
```

**Good:**
```tsx
{data.alerts.length > 1 && (
  <span className={styles.count}>+{data.alerts.length - 1}</span>
)}
```

### Rule FE-8: Null-Check Nested API Fields Before Dereferencing
Before accessing nested properties on API response objects (e.g., `data.top_alert.level`), guard against `null` or `undefined` at every level. The backend may change its contract or return partial data.

**Bad:**
```tsx
const top = data.top_alert
const levelClass = LEVEL_CLASS[top.level]
```

**Good:**
```tsx
if (!data || !data.top_alert) return null
const top = data.top_alert
const levelClass = LEVEL_CLASS[top.level] || styles.info
```

### Rule FE-9: Clean Up setTimeout / setInterval in React Components
Any `setTimeout` or `setInterval` inside a React component that calls `setState` in its callback MUST be cleared on unmount. Store the handle in a `useRef` and clear it both before starting a new one and in a `useEffect` cleanup.

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
      setCopied((prev) => (prev === id ? null : prev));
      copyTimerRef.current = null;
    }, 1500);
  }).catch(() => {
    setCopied((prev) => (prev === id ? null : prev));
  });
}
```

### Rule FE-10: Async State Clears Must Use Prev Callback
When clearing a transient state flag (loading, resetting, copied, etc.) inside `.catch()` or `.finally()` of a promise chain, always use the functional `setState(prev => ...)` form. A stale promise must never overwrite state that a newer operation has already set.

**Bad:**
```tsx
api.resetCircuitBreaker(name)
  .then(() => load())
  .finally(() => { setResetting(null); });
// If user clicks Reset on A then B, A's finally clears B's resetting state.
```

**Good:**
```tsx
api.resetCircuitBreaker(name)
  .then(() => load())
  .finally(() => { setResetting((prev) => (prev === name ? null : prev)); });
```

### Rule FE-11: Polling and User-Triggered Fetches Must Share an In-Flight Guard
If a component polls on an interval AND allows user-triggered refreshes (reset, save, delete), both paths MUST check the same `inFlight` ref. Use `useRef(false)` scoped to the component, not a local `let inFlight` inside `useEffect`.

**Bad:**
```tsx
useEffect(() => {
  let inFlight = false;  // invisible to handleReset
  function tick() {
    if (inFlight) return;
    inFlight = true;
    load().finally(() => { inFlight = false; });
  }
  // ...
}, []);

function handleReset(name: string) {
  api.resetCircuitBreaker(name).then(() => load());  // bypasses guard, may stack
}
```

**Good:**
```tsx
const inFlightRef = useRef(false);

const load = useCallback(async (signal?: AbortSignal) => {
  if (inFlightRef.current) return;
  inFlightRef.current = true;
  try { /* fetch */ } finally { inFlightRef.current = false; }
}, []);

function handleReset(name: string) {
  if (inFlightRef.current) return;  // respects same guard
  api.resetCircuitBreaker(name).then(() => load());
}
```
