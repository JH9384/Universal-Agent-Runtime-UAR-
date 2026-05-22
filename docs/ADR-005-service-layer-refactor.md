# ADR-005: Service Layer Extraction

## Status

Accepted

## Context

The UAR API (`uar/api/server.py`) had grown to ~2500 lines with significant duplication:

- Event creation logic was copy-pasted between SSE (`stream_goal`), WebSocket (`stream_goal_ws`, `websocket_run`), and direct response paths.
- Recipe CRUD (GET/POST/PUT/DELETE) repeated the same auth checks, canonical guards, and owner verification in each endpoint.
- Authentication and authorization logic (API key validation, user tier checks, resource ownership) was scattered across endpoints and WebSocket handlers.
- Goal execution streaming (orchestration plan emission, event limit enforcement, adaptive backpressure, persistence) was implemented inline in both SSE and WebSocket endpoints.

This made the code difficult to test, reason about, and modify. Any change to event schema, auth rules, or recipe validation required touching multiple locations.

## Decision

Extract a service layer under `uar/services/` with these principles:

1. **Single source of truth for each concern**
   - `EventService` — all UAR event creation, formatting, and schema compliance (`uar.event.v1`)
   - `AuthService` — authentication, authorization, ownership checks, WebSocket auth parsing
   - `RecipeService` — CRUD for canonical + user recipes with persistence and validation
   - `GoalExecutionService` — unified goal execution for SSE and WebSocket, including backpressure, event limits, and persistence
   - `RateLimitService` — WebSocket rate limit gating with policy-violation close

2. **Stateless services with dependency injection**
   - Each service accepts its dependencies via constructor (e.g., `GoalExecutionService` receives `EventService` and `JsonRunStore`)
   - No global state; services are instantiated once at module level in `server.py` and injected into endpoints

3. **FastAPI endpoints become thin orchestrators**
   - Endpoints handle HTTP/WebSocket protocol concerns (request parsing, response formatting, connection lifecycle)
   - Business logic delegates entirely to services
   - Exception mapping from service exceptions to HTTP status codes is centralized in `_recipe_http_error`

## Consequences

### Positive

- **Testability**: Services can be unit-tested in isolation without spinning up a FastAPI app or TestClient
- **Consistency**: Event schema, auth rules, and recipe validation are enforced in exactly one place
- **Maintainability**: Adding a new recipe field or auth check requires modifying one service method, not N endpoints
- **Composability**: Services can be reused outside the HTTP API (CLI, background workers, tests)

### Negative / Trade-offs

- **Indirection**: Stack traces are one frame deeper; debug logging must be comprehensive inside services
- **Service lifecycle**: Services are instantiated at module import time in `server.py`; this is acceptable for stateless services but would need refactoring if stateful (e.g., DB connection pools) were introduced
- **Async boundary**: `GoalExecutionService._persist()` was initially declared `async` despite being synchronous I/O. This was corrected to synchronous to avoid misleading callers.

## Service Boundaries

| Service | Owned By | Called By |
|---|---|---|
| `EventService` | `server.py` (singleton) | `server.py`, `GoalExecutionService` |
| `AuthService` | `server.py` (singleton) | `server.py` endpoints |
| `RecipeService` | `server.py` (singleton) | `server.py` recipe endpoints |
| `GoalExecutionService` | `server.py` (singleton) | `stream_goal`, `stream_goal_ws`, `websocket_run` |
| `RateLimitService` | `server.py` (singleton) | WebSocket connection handlers |

## Migration Notes

- Old `_validate_recipe` / `_validate_recipes` helpers in `server.py` were removed; validation is now in `RecipeService`
- `get_current_user` dependency was removed; endpoints use `AuthService.authenticate()` directly
- `AdaptiveBackpressure` class moved from `server.py` to `GoalExecutionService`
- WebSocket connection cap counter (`_ws_conn_counter`) remains in `server.py` because it's a connection-level protocol concern
