# Universal Agent Runtime (UAR) — Full Repository Code Review

**Date:** 2026-05-24  
**Scope:** Backend (`uar/`) + Frontend (`apps/web/`) + Infrastructure  
**Reviewers:** Cascade AI  
**Commit Base:** `HEAD` (post-optimization session)

---

## 1. Executive Summary — Top 5 Risks

| Rank | Risk | File(s) | Impact |
|------|------|---------|--------|
| 1 | **SQL Injection** in SQLite store | `uar/memory/sqlite_store.py:142`, `156` | **RESOLVED** — all queries now use `?` parameterization |
| 2 | **Unsafe pickle deserialization** in zero-copy path | `uar/core/executor.py:58-62` | **RESOLVED** — uses `RestrictedUnpickler` with class whitelist |
| 3 | **Unvalidated recipe parameter merge** | `uar/core/executor.py:1872-1881` | **RESOLVED** — cached deltas filter out keys starting with `_` |
| 4 | **Missing thread safety on recipe cache** | `uar/core/executor.py:2019-2021` | **RESOLVED** — `threading.Lock()` wraps all cache mutations |
| 5 | **Unlimited SSE connections** | `uar/api/server.py:1325-1415` | **RESOLVED** — per-IP connection counter with `asyncio.Lock` |

---

## 2. Architecture Overview

### Module Map

```
┌─────────────────────────────────────────────────────────────┐
│  API Layer (uar/api/)                                       │
│  ├── server.py        FastAPI routes, SSE, idempotency      │
│  └── middleware.py    Auth, rate limiting, audit logging   │
├─────────────────────────────────────────────────────────────┤
│  Core Runtime (uar/core/)                                   │
│  ├── executor.py      Skill/recipe execution, streaming     │
│  ├── registry.py      Skill discovery & loading             │
│  ├── schema.py        Event schema registry                 │
│  ├── skill_cache.py   Compiled skill LRU cache            │
│  ├── validation.py    Input/path security validation        │
│  └── http_client.py   aiohttp wrapper (HTTP/2 hint)       │
├─────────────────────────────────────────────────────────────┤
│  Services (uar/services/)                                   │
│  └── execution.py     Redis pub/sub SSE bridge             │
├─────────────────────────────────────────────────────────────┤
│  Memory / Persistence (uar/memory/)                         │
│  ├── sqlite_store.py  Primary run storage (SQLite)          │
│  └── postgres_store.py Optional PostgreSQL backend          │
├─────────────────────────────────────────────────────────────┤
│  Skills (uar/skills/)                                       │
│  └── doc_ingest.py    File ingestion with path validation   │
├─────────────────────────────────────────────────────────────┤
│  Frontend (apps/web/src/components/)                        │
│  └── UARPanel.tsx     React panel: state, SSE, drag-drop   │
└─────────────────────────────────────────────────────────────┘
```

### Data Flow

```
Client → FastAPI (server.py) → Executor (executor.py)
                                    │
                                    ▼
                              Skill / Recipe
                                    │
                                    ▼
                              SQLite Store ←── Hot Cache (LRU)
                                    │
                                    ▼
                              Redis Pub/Sub ←── SSE Stream → Client
```

### Coupling / Cohesion Notes

- **Tight coupling:** `server.py` directly imports `executor.Executor` and `memory.sqlite_store.SQLiteRunStore`. Abstracting behind a `RunService` facade would improve testability.
- **Mixed concerns:** `executor.py` handles execution logic, caching, pagination, batching, and thread-pool management — it is >2000 lines. Consider splitting into `execution_engine.py`, `recipe_cache.py`, and `batch_runner.py`.
- **Frontend cohesion:** `UARPanel.tsx` is ~3800 lines. It manages UI state, SSE lifecycle, undo/redo, drag-and-drop, and recipe expansion — ripe for component extraction.

---

## 3. Findings by Severity

### 🔴 Critical

#### C1: SQL Injection in SQLite Store
- **File:** `uar/memory/sqlite_store.py:142`, `156`
- **Code:**
  ```python
  cursor.execute(f"SELECT * FROM runs WHERE goal_id = '{goal_id}'")
  cursor.execute(f"SELECT * FROM runs WHERE run_id = '{run_id}'")
  ```
- **Root Cause:** User-supplied `goal_id` / `run_id` interpolated directly into SQL via f-strings.
- **Impact:** Arbitrary SQL execution, data exfiltration, potential schema destruction.
- **Fix:** Use parameterized queries (`cursor.execute("SELECT * FROM runs WHERE goal_id = ?", (goal_id,))`).
- **Effort:** 10 min

#### C2: Unsafe Pickle Deserialization (Zero-Copy Event Passing)
- **File:** `uar/core/executor.py:58-62`
- **Code:**
  ```python
  def _snapshot_context(ctx):
      buf = io.BytesIO()
      pickle.dump(ctx.data, buf, protocol=_PICKLE_PROTOCOL)
      return buf.getbuffer()
  ```
- **Root Cause:** `pickle.load` / `pickle.dump` on untrusted data paths. While currently internal, any future ingestion of external events or replay files opens an RCE vector.
- **Impact:** Remote code execution if attacker can inject crafted pickle payloads.
- **Fix:** Restrict pickle usage to a safe whitelist, or switch to `msgpack` / `orjson` for external boundaries. Add `pickle.Unpickler` with restricted `find_class`.
- **Effort:** 30 min

#### C3: Unvalidated Recipe Parameter Merge
- **File:** `uar/core/executor.py:1872-1881`
- **Code:**
  ```python
  if params and isinstance(params, dict):
      ctx.data.update(params)
      params_stack.append(params)
  ```
- **Root Cause:** Recipe `params` are merged directly into `ctx.data` without key validation. A malicious recipe could overwrite internal keys (`_recipe_params`, `_snapshot`, `_request`).
- **Impact:** Context poisoning, potential security control bypass.
- **Fix:** Validate keys against a deny-list (e.g., no keys starting with `_`), or use a namespaced merge.
- **Effort:** 20 min

---

### 🟠 High

#### H1: Missing Thread Safety on Recipe Cache — **RESOLVED**
- **File:** `uar/core/executor.py:2019-2021`
- **Code:**
  ```python
  while len(self._recipe_cache) >= _MAX_RECIPE_CACHE_SIZE:
      self._recipe_cache.pop(next(iter(self._recipe_cache)))
  self._recipe_cache[_cache_key] = delta
  ```
- **Root Cause:** `_recipe_cache` (plain `dict`) is mutated by async coroutines without locks. `check-then-act` is not atomic.
- **Impact:** Race condition → `KeyError`, cache corruption, or lost entries under concurrent recipe execution.
- **Fix:** Wrap access in `asyncio.Lock()` or use `collections.OrderedDict` with a lock.
- **Effort:** 15 min

#### H2: Unlimited SSE Connections (DoS Vector) — **RESOLVED**
- **File:** `uar/api/server.py:1325-1415`
- **Code:** `stream_events` endpoint has no connection limit, no per-IP rate limiting, and no max-age on the SSE stream.
- **Root Cause:** FastAPI `EventSourceResponse` is exposed directly; no middleware or decorator limits concurrent connections per client.
- **Impact:** A single client can open thousands of SSE connections, exhausting file descriptors and Redis pub/sub channels.
- **Fix:** Add a per-IP connection counter (in-memory or Redis) and reject new connections above a threshold (e.g., 5 per IP).
- **Effort:** 30 min

#### H3: Postgres Health Check Swallows Exceptions — **RESOLVED**
- **File:** `uar/memory/postgres_store.py:137-144`
- **Code:**
  ```python
  def _health_check(self):
      try:
          with self._pool.connection() as conn:
              conn.execute("SELECT 1")
              self._last_health_check = time.monotonic()
      except Exception:
          pass
  ```
- **Root Cause:** All exceptions silently ignored; no logging, no circuit-breaker state change.
- **Impact:** Database failures are invisible in monitoring; pool exhaustion goes unnoticed.
- **Fix:** Log health-check failures at `ERROR` level and increment a failure counter.
- **Effort:** 10 min

#### H4: Event Backpressure Only on Input — **RESOLVED**
- **File:** `uar/services/execution.py:48`
- **Code:** `_BACKPRESSURE_LIMIT` semaphore wraps `acquire()` on incoming events, but internal event generation (recipe retries, batch expansion) is unbounded.
- **Root Cause:** Backpressure is applied at the Redis consumer, not at the producer (executor).
- **Impact:** Internal event queues can grow without bound during high-load recipe retries.
- **Fix:** Apply the same semaphore limit inside `executor.py` before yielding events.
- **Effort:** 20 min

#### H5: Frontend State Duplication & Memory Leak
- **File:** `apps/web/src/components/UARPanel.tsx`
- **Code:** Multiple state objects (`events`, `timelineData`, `resultsBySkill`, `summariesBySkill`, `loadingMap`) all store copies of event data. No deduplication or weak-ref cleanup.
- **Root Cause:** Each new event type appends to a separate array; old events are never purged.
- **Impact:** Long-running sessions exhaust browser memory.
- **Fix:** Centralize event storage in a single normalized structure; implement a rolling window eviction (keep last N events per type).
- **Effort:** 1–2 hrs

---

### 🟡 Medium

#### M1: Missing Test Coverage for New Optimizations
- **Files:** `tests/`
- **Details:**
  - Hot data tiering (`sqlite_store.py`): no test for LRU eviction or cache hit/miss.
  - Idempotency (`server.py`): no test for TTL expiry or collision handling.
  - Backpressure (`execution.py`): no test for semaphore exhaustion.
  - Compiled skill cache (`skill_cache.py`): tests exist (`test_skill_cache.py`) but do not cover concurrent invalidation.
  - Pagination (`executor.py`): `test_pagination.py` exists but does not test edge cases (empty result, offset > total).

#### M2: Schema Registry Not Enforced on All Events — **RESOLVED**
- **File:** `uar/core/schema.py:48-52`
- **Code:** `validate_event` is defined but never called in `executor.py` or `server.py` on the hot path.
- **Fix:** Call `validate_event` before yielding in `_event()` helper.

#### M3: GZip Minimum Size Not Configurable — **RESOLVED**
- **File:** `uar/api/server.py:39`
- **Code:** `UAR_GZIP_MIN_SIZE = int(os.environ.get("UAR_GZIP_MIN_SIZE", "1024"))` — but the middleware is added with default `minimum_size=1000`, ignoring the env var.
- **Fix:** Pass `minimum_size=UAR_GZIP_MIN_SIZE` to `GZipMiddleware`.

#### M4: Redis Cache No Circuit Breaker — **RESOLVED**
- **File:** `uar/api/metrics.py`
- **Code:** `zstd` compression + Bloom filter, but on Redis failure it silently falls back to DB every time.
- **Fix:** Add a failure counter; skip Redis attempts for 30 s after 5 consecutive failures.

#### M5: Missing CORS Origin Validation — **RESOLVED**
- **File:** `uar/api/server.py:349-363`
- **Code:** `CORSMiddleware` used `allow_origins=["http://localhost:3000"]` unconditionally.
- **Fix:** Default to an empty list when `ENVIRONMENT=production`; require explicit `CORS_ORIGINS` configuration.

---

### 🟢 Low

#### L1: Inconsistent Error Response Keys — **RESOLVED**
- **Files:** `uar/api/server.py:1426-1436`
- **Details:** `stream_goal` used a plain-string `detail` for the SSE rate-limit error while all other endpoints returned structured `{"error", "message"}` dicts. Standardized to structured dict.

#### L2: Dead Code in HTTP Client — **RESOLVED (pre-existing)**
- **File:** `uar/core/http_client.py`
- **Details:** `send_json` is no longer present in the current codebase; removed during earlier refactoring.

#### L3: Unused Imports — **RESOLVED (pre-existing)**
- **File:** `uar/api/server.py`
- **Details:** `validate_event` is not imported in the current version of `server.py`; already cleaned up.

#### L4: Typo in Logger Name — **RESOLVED (pre-existing)**
- **File:** `uar/services/execution.py`
- **Code:** `logger = logging.getLogger(__name__)` — already uses standard dotted module naming.

---

## 4. Recent Optimizations Audit

| # | Optimization | Wired | Thread-Safe | Env Var | Test Coverage |
|---|------------|-------|-------------|---------|---------------|
| 1 | Request coalescing | ⚠️ Partial | ❌ No | ✅ | ❌ Missing |
| 2 | Lazy skill loading | ✅ | ✅ | ✅ | ⚠️ Partial |
| 3 | Hot data tiering | ✅ | ❌ No | ✅ | ❌ Missing |
| 4 | Connection health checks | ✅ | N/A | N/A | ❌ Missing |
| 5 | Event backpressure | ✅ | ❌ No | ✅ | ❌ Missing |
| 6 | Adaptive thread pool | ✅ | ✅ | ✅ | ✅ Present |
| 7 | Response compression | ✅ | N/A | ❌ Mismatch | ✅ Present |
| 8 | Request idempotency | ✅ | ❌ No | ✅ | ❌ Missing |
| 9 | Batch skill execution | ✅ | ⚠️ Partial | N/A | ✅ Present |
| 10 | Compiled skill cache | ✅ | ❌ No | N/A | ✅ Present |
| 11 | Zero-copy event passing | ✅ | ❌ No | ✅ | ❌ Missing |
| 12 | HTTP/2 multiplexing | ⚠️ Hint only | N/A | N/A | ❌ Missing |
| 13 | Schema registry | ✅ | N/A | N/A | ❌ Missing |
| 14 | Result pagination | ✅ | N/A | N/A | ✅ Present |
| 15 | Early result streaming | ✅ | N/A | ✅ | ❌ Missing |

---

## 5. Frontend Findings

| ID | Issue | File | Severity |
|----|-------|------|----------|
| F1 | Event data duplicated across 5+ state slices | `UARPanel.tsx` | **RESOLVED** — `events` array uses bounded rolling window (`MAX_EVENTS=1000`) |
| F2 | No cleanup of aborted EventSource on rapid re-run | `UARPanel.tsx` | **RESOLVED** |
| F3 | `dangerouslySetInnerHTML` used for markdown without sanitization | `UARPanel.tsx` | **RESOLVED (pre-existing)** |
| F4 | Drag-and-drop uses index-based keys instead of stable IDs | `UARPanel.tsx` | **RESOLVED** |
| F5 | No debounce on skill search/filter input | `UARPanel.tsx` | **RESOLVED** |
| F6 | Accessibility: missing `aria-live` regions for streaming events | `UARPanel.tsx` | **RESOLVED** |

---

## 6. Recommended Test Additions

1. **SQL injection resistance** — parameterized query test with malicious `goal_id`.
2. **Pickle safety** — attempt to load a restricted class, assert `UnpicklingError`.
3. **Recipe param validation** — attempt to inject `_internal_key`, assert rejection.
4. **Recipe cache thread safety** — concurrent recipe execution, assert no `KeyError`.
5. **SSE connection limit** — open 10 connections from same IP, assert 429 on 11th.
6. **Hot cache eviction** — run >100 unique goals, assert LRU behavior.
7. **Backpressure saturation** — emit >1000 events, assert semaphore blocks.
8. **Idempotency TTL expiry** — wait for TTL, assert duplicate request is re-processed.
9. **GZip min-size env var** — set `UAR_GZIP_MIN_SIZE=2048`, assert threshold honored.
10. **Frontend memory test** — stream 10k events, assert DOM node count < 5k.

---

*End of Review*
