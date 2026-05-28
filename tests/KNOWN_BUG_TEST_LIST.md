# Known Bug Test List

Comprehensive checklist of bug patterns found across review sessions.
Each entry includes: **status** (fixed/open), **severity**, **pattern description**,
**affected files**, and **test to verify**.

---

## Category A: Store & Persistence

### A1. Store field-name mapping (run_id / goal_id) — FIXED
- **Severity**: High
- **Pattern**: `append()`, `append_many()`, `append_async()` used
  `getattr(record, "id", "")` and `getattr(record, "goal", {}).get("id", "")`
  which always return `""` for real `RunRecord` objects (fields are `run_id`/`goal_id`).
- **Files**: `uar/memory/postgres_store.py`, `uar/memory/sqlite_store.py`
- **Fix**: `getattr(record, "run_id", getattr(record, "id", ""))` and equivalent for `goal_id`.
- **Test**:
  ```python
  def test_store_append_maps_run_id_and_goal_id():
      from uar.core.contracts import RunRecord
      from uar.memory.sqlite_store import SqliteRunStore

      store = SqliteRunStore(path=":memory:")
      store.append(RunRecord(run_id="r1", goal_id="g1", skills=["noop"], status="completed"))
      rows = store.list_records()
      assert rows[0]["run_id"] == "r1"
      assert rows[0]["goal_id"] == "g1"
  ```

### A2. SQLite purge_old_records timestamp mismatch — FIXED
- **Severity**: Critical
- **Pattern**: `created_at` defaulted to `julianday('now')` (~2.46M) while
  `purge_old_records` computed Unix epoch cutoff (~1.7B).
  `DELETE WHERE created_at < cutoff` was always false → **never deleted anything**.
- **File**: `uar/memory/sqlite_store.py`
- **Fix**: `CASE WHEN created_at > 1e9 THEN datetime(created_at, 'unixepoch') ELSE datetime(created_at) END`
- **Test**:
  ```python
  def test_sqlite_purge_actually_removes_old_rows():
      # Insert one old (Unix epoch), one new (Julian day) record.
      # Purge with 5-day retention; assert exactly 1 removed.
  ```

### A3. JsonRunStore purge_old_records non-existent key — FIXED
- **Severity**: High
- **Pattern**: `purge_old_records` checked `record.get("timestamp")`, but
  `append()` never wrote that key. Records always lacked it → purge never removed anything.
- **File**: `uar/memory/json_store.py`
- **Fix**: Inject `created_at` in `append()`, check `created_at` in purge.
- **Test**:
  ```python
  def test_json_purge_actually_removes_old_lines():
      # Write one recent record via append(), one old via raw write.
      # Purge with 5-day retention; assert exactly 1 removed.
  ```

### A4. PipelineContext.events O(n) eviction — FIXED
- **Severity**: High
- **Pattern**: `events` was a plain `list`; eviction used `pop(0)` which is O(n)
  and caused unbounded growth under high event volume.
- **File**: `uar/core/contracts.py`
- **Fix**: Use `collections.deque(maxlen=_max_events)` in `__post_init__`.
- **Test**:
  ```python
  def test_pipeline_context_events_is_deque():
      from uar.core.contracts import PipelineContext, GoalSpec
      ctx = PipelineContext(goal=GoalSpec(id="g", user_intent="t", objective="t"))
      assert isinstance(ctx.events, collections.deque)
  ```

### A5. PipelineContext overflow file leak — FIXED
- **Severity**: Medium
- **Pattern**: When `UAR_CONTEXT_DISK_OVERFLOW=true`, each `PipelineContext` opened
  a temp file that was never explicitly closed in parallel execution copies.
- **File**: `uar/core/contracts.py`
- **Fix**: Add `__del__` that calls `close()` so GC cleans up even without explicit `close()`.
- **Test**:
  ```python
  def test_pipeline_context_del_closes_overflow_file():
      # Create ctx with overflow, call close() (not __del__ directly),
      # assert file handle is closed.
  ```

### A6. PostgresRunStore purge_old_records missing — FIXED
- **Severity**: Medium
- **Pattern**: `RunStoreProtocol` added `purge_old_records`, but `PostgresRunStore`
  already had an implementation (no bug, but protocol completeness).
- **File**: `uar/memory/postgres_store.py`
- **Test**:
  ```python
  def test_postgres_run_store_has_purge_old_records():
      from uar.memory.postgres_store import PostgresRunStore
      assert hasattr(PostgresRunStore, "purge_old_records")
  ```

---

## Category B: Async / Sync Boundaries

### B1. asyncio.run() inside running event loop — FIXED
- **Severity**: High
- **Pattern**: `asyncio.run()` raises `RuntimeError` when called from a running
  event loop (e.g., FastAPI request handler).
- **File**: `uar/skills/autonomi_storage.py`
- **Fix**: Use `run_sync_safe()` from `uar.core.async_utils` instead.
- **Test**:
  ```python
  def test_run_sync_safe_from_running_loop():
      # Already in test_store_and_contracts.py
  ```

### B2. Deprecated asyncio.get_event_loop() — FIXED
- **Severity**: Medium
- **Pattern**: `asyncio.get_event_loop()` is deprecated in Python 3.10+ and
  raises `DeprecationWarning` / fails if no current loop.
- **File**: `uar/core/http_client.py`
- **Fix**: Replace with `run_sync_safe(sess.close())`.
- **Test**: Verify no `get_event_loop` string in `http_client.py`.

### B3. run_sync_safe coroutine not closed on exception — FIXED
- **Severity**: Medium
- **Pattern**: If `run_sync_safe`'s thread-executor path raised, the coroutine
  object could be left unclosed, leaking async resources.
- **File**: `uar/core/async_utils.py`
- **Fix**: `_run_in_new_loop` catches `BaseException`, calls `coro.close()`, re-raises.
- **Test**:
  ```python
  def test_run_sync_safe_closes_coro_on_exception():
      import asyncio
      async def _bad():
          raise ValueError("x")
      coro = _bad()
      with pytest.raises(ValueError):
          run_sync_safe(coro)
      assert coro.cr_code is None or coro.cr_frame is None  # closed
  ```

---

## Category C: Error Handling & Conventions

### C1. skill_guard status convention violation — FIXED
- **Severity**: Medium
- **Pattern**: Framework wrapper skills used `status="failed"` but convention
  is `"error"` for infra/framework failures, `"failed"` for compute skills.
- **File**: `uar/skills/advanced_integrations.py`
- **Fix**: Revert all framework wrappers to default `"error"`.
- **Test**:
  ```python
  def test_skill_guard_default_status_is_error():
      from uar.core.skill_utils import skill_guard
      @skill_guard("Framework Op")
      def boom(ctx): raise RuntimeError()
      assert boom(None)["status"] == "error"
  ```

### C2. require_package('') unreadable error message — FIXED
- **Severity**: Low
- **Pattern**: Empty string package produced `" not installed. pip install "`.
- **File**: `uar/core/skill_utils.py`
- **Fix**: Append `"<empty>"` to missing list instead of `""`.
- **Test**:
  ```python
  def test_require_package_empty_string_clear_message():
      from uar.core.skill_utils import require_package
      result = require_package("")
      assert "<empty>" in result["error"]
  ```

### C3. PathSecurityError returns bare string instead of dict — FIXED
- **Severity**: Medium
- **Pattern**: `except PathSecurityError` returned `"Error: ..."` string instead
  of a structured dict with `status: "failed"`.
- **Files**: `uar/skills/doc_ingest.py`, `uar/skills/doc_ingest_enhanced.py`
- **Fix**: Return `{"status": "failed", "error": "...", "documents": []}`.

---

## Category D: Unhandled JSONDecodeError — FIXED

### D1. services/execution.py temp-file replay — FIXED
- **Severity**: Medium
- **Pattern**: `_persist_from_file` reads a JSONL temp file and calls
  `json.loads(line)` without `try/except`. A single corrupted line crashes the
  entire replay / persistence.
- **File**: `uar/services/execution.py` (3 locations, lines ~375, ~408, ~427)
- **Fix**: Wrap each `json.loads` in `try/except json.JSONDecodeError: continue`.
- **Test**:
  ```python
  def test_persist_from_file_skips_corrupted_lines():
      # Write valid JSON line + corrupted line + valid line to temp file.
      # Call _persist_from_file; assert 2 events returned, corrupted skipped.
  ```

### D2. MCP server payload parse — FIXED
- **Severity**: Medium
- **Pattern**: `_read_message` reads from `sys.stdin` and calls `json.loads(raw)`
  without error handling. Malformed JSON crashes the MCP server.
- **File**: `uar/mcp/server.py:50`
- **Fix**: Wrap in `try/except json.JSONDecodeError` and return `{}` or raise a
  protocol-specific error.
- **Test**:
  ```python
  def test_mcp_server_handles_invalid_json_gracefully():
      # Mock stdin with invalid JSON; assert no unhandled exception.
  ```

### D3. CursorToken.decode tampered token — FIXED
- **Severity**: Medium
- **Pattern**: `CursorToken.decode` does `json.loads(raw)` on base64-decoded data
  without error handling. A tampered or truncated token causes unhandled crash.
- **File**: `uar/core/pagination.py:57`
- **Fix**: Wrap in `try/except (json.JSONDecodeError, binascii.Error)` and raise
  `ValueError("Invalid cursor token")`.
- **Test**:
  ```python
  def test_cursor_token_decode_rejects_malformed_token():
      with pytest.raises(ValueError):
          CursorToken.decode("not-valid-base64!!!")
  ```

### D4. objects/store.py SQLite JSON load — FIXED
- **Severity**: Low
- **Pattern**: Loads `record_json` and `event_json` from SQLite without
  validating JSON. Corrupted DB rows crash the store on init.
- **File**: `uar/objects/store.py` (lines ~117, ~120)
- **Fix**: Wrap in `try/except json.JSONDecodeError` and skip corrupted rows
  with a warning log.
- **Test**:
  ```python
  def test_object_store_skips_corrupted_db_rows():
      # Insert a row with invalid JSON into objects table.
      # Load store; assert it initializes without crash.
  ```

### D5. core/cache_backends.py Redis cache JSON — FIXED
- **Severity**: Low
- **Pattern**: `json.loads(str(raw))` on Redis cache values without error handling.
  Corrupted cache entries cause silent or loud failures.
- **File**: `uar/core/cache_backends.py` (lines ~371, ~414)
- **Fix**: Wrap in `try/except json.JSONDecodeError` and treat as cache miss.
- **Test**:
  ```python
  def test_redis_cache_treats_invalid_json_as_miss():
      # Mock Redis client.get() to return "not-json".
      # Assert cache read returns None (miss) without exception.
  ```

### D6. core/skill_cache.py decompressed JSON — FIXED
- **Severity**: Low
- **Pattern**: `json.loads(zlib.decompress(raw))` and similar paths lack
  `JSONDecodeError` handling. Corrupted compressed entries crash.
- **File**: `uar/core/skill_cache.py` (lines ~212, ~274)
- **Fix**: The outer `try/except Exception: return None` already catches this,
  but it is too broad. Narrow to `json.JSONDecodeError` and log.

### D7. sigmatics_integration CLI stdout JSON — FIXED
- **Severity**: Low
- **Pattern**: Assumes CLI stdout is valid JSON. Error output or empty stdout
  causes unhandled `JSONDecodeError`.
- **File**: `uar/core/sigmatics_integration.py:180`
- **Fix**: Validate `result.returncode == 0 and result.stdout` before `json.loads`.
- **Test**:
  ```python
  def test_sigmatics_handles_non_json_stdout():
      # Mock subprocess.run with returncode=0 but stdout="error msg".
      # Assert function returns None instead of crashing.
  ```

### D8. schema_validation remote schema fetch — FIXED
- **Severity**: Low
- **Pattern**: Fetches remote schema via HTTP and calls `json.loads()` without
  handling decode errors or non-JSON responses (e.g., 404 HTML page).
- **File**: `uar/uor/schema_validation.py:116`
- **Fix**: Check HTTP content-type and wrap `json.loads` in `try/except`.

---

## Category E: Dead Code & Logic Issues

### E1. executor.py _executed_hierarchical dead variable — FIXED
- **Severity**: Low
- **Pattern**: `_executed_hierarchical = False` was never set to `True`.
  The `if not _executed_hierarchical:` after a guaranteed `return` was always true.
- **File**: `uar/core/executor.py`
- **Fix**: Removed variable and redundant condition.

### E2. executor.py recipe_cache metrics not thread-safe — FIXED
- **Severity**: Low
- **Pattern**: `_recipe_cache_hits` / `_recipe_cache_misses` are incremented
  under `_recipe_cache_lock`, but the metrics yield at the end reads them
  without the lock held.
- **File**: `uar/core/executor.py`
- **Fix**: Snapshot metrics under lock before yielding.
- **Test**: Stress-test hierarchical execution with concurrent recipe cache access.

### E3. execution.py temp file leak with background persist — FIXED
- **Severity**: Low
- **Pattern**: If `_bg_persist` is True and an exception occurs before the async
  task starts, the temp file is never unlinked. Also, `_bg_persist` was defined
  inside the `try` block, causing `UnboundLocalError` in `finally` if an
  exception occurred before it was assigned.
- **File**: `uar/services/execution.py`
- **Fix**: Moved `_bg_persist` initialization before the `try` block. Always
  unlink the temp file in `finally` (the async task's cleanup is a nice-to-have
  but `finally` is the safety net; duplicate unlink is harmless).

---

## Category F: Security & Validation

### F1. safe_eval subscript bypass — FIXED
- **Severity**: Medium
- **Pattern**: `safe_eval` rejected `"__"` but allowed `"_" + "_"` concatenation
  in subscript slices (e.g., `d['__'+'class__']`).
- **File**: `uar/core/sandbox.py`
- **Fix**: Evaluate subscript values before checking for dunder strings.
- **Test**:
  ```python
  def test_safe_eval_rejects_concatenated_dunder_subscript():
      with pytest.raises(SandboxError):
          safe_eval("d['__'+'class__']", {"d": {}})
  ```

### F2. doc_ingest path traversal validation — PARTIALLY FIXED
- **Severity**: High
- **Pattern**: `validate_path_security` is called, but some code paths may bypass
  it or not re-validate resolved paths after symlink resolution.
- **Files**: `uar/skills/doc_ingest.py`, `uar/skills/doc_ingest_enhanced.py`
- **Test**: Fuzz with symlink chains pointing outside `ALLOWED_ROOT`.

---

## Category G: Conventions & Lint

### G1. 3 blank lines between top-level definitions — FIXED
- **Severity**: Low
- **Pattern**: `advanced_integrations.py` had 3 blank lines between function defs
  (PEP8 requires 2).
- **File**: `uar/skills/advanced_integrations.py`
- **Fix**: Reduced to 2 blank lines throughout.

### G2. Missing trailing newline at EOF — FIXED
- **Severity**: Low
- **Pattern**: `advanced_integrations.py` lacked trailing newline.
- **File**: `uar/skills/advanced_integrations.py`
- **Fix**: Added `\n` terminator.

---

## How to Run This Test List

```bash
# All known-bug regression tests (current)
python -m pytest tests/test_store_and_contracts.py -v

# Full suite (excludes adversarial / benchmark)
python -m pytest tests/ -x --ignore=tests/adversarial_audit.py \
  --ignore=tests/benchmark_skills.py -q

# Lint check on modified files
python -m ruff check uar/memory/sqlite_store.py uar/memory/json_store.py \
  uar/skills/advanced_integrations.py uar/core/skill_utils.py \
  uar/core/executor.py tests/test_store_and_contracts.py
```

## Legend

| Symbol | Meaning |
|--------|---------|
| FIXED  | Bug has been fixed and regression test added. |
| OPEN   | Bug identified but not yet fixed (needs PR). |
