# UAR Codebase Reuse Review

> Completed 2026-05-27. All changes committed. 889/889 tests passing.

---

## Shared Infrastructure Created

### 1. `uar/core/async_utils.py` — `run_sync_safe(coro)`

**Problem:** Multiple locations ran async coroutines from sync code using
`asyncio.run()` or manual `new_event_loop()` detection. These patterns were
buggy (coroutine leaks on exception) and crashed when called from an already
running event loop (FastAPI / uvicorn).

**Locations fixed:**
| File | Before | After |
|---|---|---|
| `uar/skills/autonomi_storage.py` | `asyncio.run(asyncio.wait_for(...))` | `run_sync_safe(asyncio.wait_for(...))` |
| `uar/core/http_client.py` | `asyncio.get_event_loop().run_until_complete(sess.close())` | `run_sync_safe(sess.close())` |
| `uar/core/executor.py` | 25-line manual loop detection + `asyncio.run()` | `run_sync_safe(asyncio.wait_for(...))` |

**Net:** `-25 lines` in executor, consistent safe async→sync bridge everywhere.

---

### 2. `uar/memory/base_store.py` — `RunStoreProtocol` + `run_record_from_dict()` + `get_store()`

**Problem:**
- `RunRecord(**row)` crashed with `TypeError` when store rows contained
  backend-specific columns (`created_at`, `id`, `metadata`) not present in
  `RunRecord`.
- CLI and server code hardcoded `JsonRunStore()`, ignoring `UAR_DATABASE_URL`.
- Store interface was inconsistent (`get_by_run_id` missing on `JsonRunStore`).

**Shared helper:** `run_record_from_dict(row)` — filters dict to only
`RunRecord` fields before construction. Single source of truth.

**Shared factory:** `get_store()` — reads `UAR_DATABASE_URL` / `UAR_SQLITE_PATH`
and returns `PostgresRunStore` / `SqliteRunStore` / `JsonRunStore` automatically.

**Locations fixed:**
| File | Before | After |
|---|---|---|
| `uar/cli/main.py` | `JsonRunStore()` x4 | `get_store()` x4 |
| `uar/cli/run.py` | `JsonRunStore()` x3 | `get_store()` x3 |
| `uar/api/server.py` `_retention_purge_loop` | `JsonRunStore()` | `get_store()` |
| `uar/api/server.py` `provenance` | `SqliteRunStore()` (hardcoded!) | module-level `store` |
| `uar/services/execution.py` | type `Optional[JsonRunStore]` | type `Optional[RunStoreProtocol]` |
| `uar/memory/json_store.py` | no `get_by_run_id` | added `get_by_run_id` |
| `uar/memory/base_store.py` | `RunStoreProtocol` missing `get_by_run_id` | added |

---

## Bugs Found & Fixed During Reuse Review

### Bug 1: `postgres_store.py` — silent data corruption (High)
- `append()`, `append_many()`, `append_async()` used `getattr(record, "id", "")`.
  Since `RunRecord` has `run_id` (not `id`), every write silently stored `""`.
- Fixed: `getattr(record, "run_id", getattr(record, "id", ""))` + equivalent for
  `goal_id`.

### Bug 2: `contracts.py` — `PipelineContext.events` O(n) eviction + file leak (High)
- `events` was a `list`; eviction used `pop(0)` which is O(n).
- Parallel skill copies opened temp overflow files that were never closed.
- Fixed: `collections.deque(maxlen=...)` in `__post_init__` for O(1) eviction.
  Added `__del__` to guarantee overflow file cleanup.

### Bug 3: `autonomi_storage.py` — `asyncio.run()` crash in running loop (High)
- Circuit-breaker lambda called `asyncio.run()` — crashes inside FastAPI.
- Fixed: `run_sync_safe()` from `async_utils`.

### Bug 4: `http_client.py` — deprecated `asyncio.get_event_loop()` (Medium)
- `close_all_sessions()` used deprecated API, fails in Python 3.10+ without loop.
- Fixed: `run_sync_safe(sess.close())`.

### Bug 5: `server.py` readiness probe — race condition (Medium)
- `.health_check` filename was shared across concurrent probes.
- Fixed: per-probe unique filename `.health_check_{pid}_{task_id}`.

---

## Reuse Stats

| Metric | Value |
|---|---|
| New shared files | `async_utils.py`, `base_store.py` |
| Files modified for reuse | 14 |
| Lines removed (duplication) | ~40 |
| Lines added (shared helpers + tests) | ~60 |
| Net diff | `-6 lines` (more functionality, less code) |
| Tests added | 11 (`test_store_and_contracts.py`) |
| Total tests | 889/889 passing |

---

## Remaining `RunRecord(**)` constructions (intentional)

These construct `RunRecord` from event streams, not from store rows, so they
do **not** need `run_record_from_dict`:

- `uar/core/executor.py:1821` — `run_record_from_events()` result
- `uar/core/replay.py:78` — `run_record_from_events()` result
- `uar/core/distributed.py:283` — `run_record_from_events()` result

All three are building fresh records from validated event payloads where no
store-internal columns exist.

---

## Test Commands

```bash
# Fast subset
python -m pytest tests/test_store_and_contracts.py tests/test_pipeline.py tests/test_api.py -q

# Full suite
python -m pytest tests/ -q --tb=short

# Regression gate
make gate
```
