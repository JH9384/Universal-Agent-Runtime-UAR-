# UAR Service Layer Architecture

> **Purpose**: Eliminate duplicated code, reduce code smell, and improve
> agent comprehension by centralising business logic.

## Before (Problems)

The API layer (`uar/api/server.py`) had severe duplication:

- `create_event()` defined **3 times** across SSE + 2 WebSocket handlers
- Auth checks (`if not user_info: raise HTTPException(401)`) repeated in
  every recipe CRUD endpoint
- Error response dicts built manually in **10+ places**
- Event limit & persistence retry logic duplicated across 3 streaming paths
- Recipe CRUD had identical boilerplate for canonical-guard + owner-check

This violated DRY, made testing difficult, and meant schema changes
required edits in N places.

## After (Architecture)

```
┌─────────────────────────────────────────────┐
│  Entry Points (thin)                        │
│  ┌─────────┐ ┌──────────┐ ┌─────────────┐ │
│  │ Routers │ │ WebSocket│ │ SSE Handler │ │
│  │ (server)│ │ (server) │ │ (server)    │ │
│  └────┬────┘ └────┬─────┘ └──────┬──────┘ │
└───────┼───────────┼──────────────┼────────┘
        │           │              │
        └───────────┴──────────────┘
                    │
        ┌───────────▼──────────────┐
        │   Service Layer          │
        │   uar/services/          │
        │                          │
        │  ┌────────────────────┐ │
        │  │ AuthService        │ │ ← auth checks, owner validation
        │  ├────────────────────┤ │
        │  │ EventService       │ │ ← single source of truth for events
        │  ├────────────────────┤ │
        │  │ GoalExecutionService│ │ ← unified streaming (SSE + WS)
        │  ├────────────────────┤ │
        │  │ RecipeService      │ │ ← CRUD with persistence
        │  ├────────────────────┤ │
        │  │ RateLimitService   │ │ ← key building + checking
        │  └────────────────────┘ │
        └───────────┬────────────┘
                    │
        ┌───────────▼──────────────┐
        │   Integration Layer        │
        │   uar/integrations/      │
        │                          │
        │  ┌────────────────────┐  │
        │  │ ConvexClient       │  │ ← real-time DB alternative
        │  ├────────────────────┤  │
        │  │ GreptileClient     │  │ ← AI code search
        │  └────────────────────┘  │
        └──────────────────────────┘
```

## Services

### `AuthService`

**Responsibility**: All authentication and authorization checks.

**Eliminates**:
- Duplicated `HTTPException(401, ...)` blocks in recipe endpoints
- Duplicated `HTTPException(403, ...)` for canonical recipe guards
- Duplicated `HTTPException(403, ...)` for owner checks
- Inline WebSocket auth parsing in both WS handlers

**Key methods**:
- `authenticate(credentials)` → user dict or None
- `require_user(credentials)` → raises 401 if anon
- `require_owner(resource, user)` → raises 403 if not owner
- `forbid_canonical(recipe_id, canon)` → raises 403 if canonical
- `parse_websocket_auth(headers, query_params)` → extracts Bearer token

### `EventService`

**Responsibility**: Single source of truth for `uar.event.v1` schema.

**Eliminates**: Three separate `create_event()` closures (SSE, WS
`/api/uar/stream/ws`, WS `/ws/run`).

**Key methods**:
- `create(...)` → canonical event dict
- `error(...)` → standardised error event
- `complete(...)` → standardised completion event
- `heartbeat(...)` → standardised heartbeat event
- `orchestration_plan(...)` → plan event with graph payload
- `emit_sse(event)` → SSE wire format (safe fallback for unserializable data)

### `GoalExecutionService`

**Responsibility**: Run goals with unified streaming.

**Eliminates**:
- Duplicated event limit enforcement (3 copies)
- Duplicated ring buffer + persistence logic
- Duplicated adaptive backpressure setup
- Duplicated `_async_event_stream` helper

**Key methods**:
- `stream_goal(goal, request_id, user_id, correlation_id, yield_persisted=False)` → async iterator of events
- `_iter_events(strategy, goal, timeout, cid)` → instance method owning Executor lifecycle

### `RecipeService`

**Responsibility**: Recipe CRUD + persistence.

**Eliminates**: Identical auth/canonical/owner boilerplate in GET/POST/
PUT/DELETE recipe endpoints.

**Key methods**:
- `list_all(user_id)` → merged canonical + user recipes
- `create(id, data, user_id)` → validates + persists
- `update(id, data, user_id)` → owner check + persist
- `delete(id, user_id)` → owner check + remove
- `load(user_id)` → safe JSON loading with corruption handling

### `RateLimitService`

**Responsibility**: Centralised rate-limit checks.

**Eliminates**: Duplicated rate limit key building + checking in HTTP
endpoints and WebSocket handlers.

**Key methods**:
- `check(client_ip, credentials)` → (allowed, tier, limits)
- `ws_close_if_denied(allowed, websocket)` → closes WS if denied

## Integrations

### `ConvexClient`

Optional real-time backend-as-a-service. Provides:
- `insert_run(record)` → persists to Convex DB
- `get_run(run_id)` → fetch by ID
- `list_runs(user_id, limit)` → paginated query
- `subscribe_events(run_id)` → real-time reactive events

Install: `pip install "universal-agent-runtime[convex]"`

### `GreptileClient`

AI-powered code search for agent comprehension.
- `query(question, repo, branch)` → natural language → code references
- `index_repo(repo, branch)` → trigger repo indexing

Install: `pip install "universal-agent-runtime[greptile]"`

## Frontend

### `apps/web-svelte/`

SvelteKit frontend using the same service abstractions:
- `src/lib/services/uar.ts` → `UARService` class encapsulates all HTTP/WS
- Shared components: `SkillSelector`, `EventStream`
- Deploys via `@sveltejs/adapter-vercel`

## Migration Guide for Agents

When modifying UAR, prefer the service layer:

1. **Adding a new endpoint**? Call a service; don't write business logic
   in the router.
2. **Changing the event schema**? Update `EventService.create()` only.
3. **Adding auth to a new resource**? Use `AuthService.require_user()`
   and `AuthService.require_owner()`.
4. **Changing rate limits**? Update `RateLimitService` only.
5. **Adding persistence backend**? Swap `JsonRunStore` for `ConvexClient`
   in `GoalExecutionService` constructor.

## Testability

All services accept dependencies via constructor injection:

```python
from uar.services import GoalExecutionService, EventService

events = EventService()
execution = GoalExecutionService(event_service=events, store=mock_store)

async for ev in execution.stream_goal(goal, "req-1", None, "cid"):
    ...
```

No FastAPI app, no WebSocket, no global state required for unit tests.
