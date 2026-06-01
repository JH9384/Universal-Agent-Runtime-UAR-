# Post-Review Bug Fixes — Batch 5 (2026-05-31)

## Summary

Fixed 3 issues identified during code review of working changes, plus regression tests for each.

## Fixes

### 1. executor.py — _coalesce_key UnboundLocalError Protection

**File:** `uar/core/executor.py`
**Lines:** 1257, 1271

**Problem:** The `_coalesce_key` variable was initialized inside the `for attempt in range(...)` loop. If an exception occurred before the loop started (e.g., during cache hit processing), the `finally` block at line 1471 would reference an undefined variable.

**Fix:** 
- Initialize `_coalesce_key = ""` before the for-loop (line 1257)
- Reset `_coalesce_key = ""` at the start of each loop iteration (line 1271)

**Test:** `test_coalesce_key_initialized_before_loop` — Source inspection test verifying initialization order.

---

### 2. sqlite_store.py — Missing DDL Commit

**File:** `uar/memory/sqlite_store.py`
**Line:** 266

**Problem:** The `_ensure_table()` method used `conn.executescript(ddl)` to create tables but did not explicitly commit. While SQLite with `isolation_level=None` auto-commits, this was inconsistent with the explicit commits for `ALTER TABLE` operations.

**Fix:** Added `conn.commit()` after `executescript(ddl)` to ensure DDL is immediately visible to other connections.

**Test:** `test_ensure_table_commits_ddl` — Opens fresh connection to verify tables exist after store creation.

---

### 3. burn_in.py — Silent Exception Swallowing

**File:** `uar/api/routers/burn_in.py`
**Line:** 131-134

**Problem:** `_set_latest_report()` silently ignored store persistence failures with a bare `except Exception: pass`. This could mask operational issues like disk full or permission errors.

**Fix:** Added logging at WARNING level when store.put_metadata fails:
```python
except Exception as exc:
    logger.warning("Failed to persist burn-in report to store: %s", exc)
```

**Test:** `test_set_latest_report_logs_store_failure` — Verifies warning is logged using pytest's caplog fixture.

---

## Test Results

```
tests/api/test_trust_spine_fixes.py::test_coalesce_key_initialized_before_loop PASSED
tests/api/test_trust_spine_fixes.py::test_ensure_table_commits_ddl PASSED
tests/api/test_trust_spine_fixes.py::test_set_latest_report_logs_store_failure PASSED

Full suite: 2969 passed, 13 skipped, 1 pre-existing YOLO failure
```

## Files Modified

1. `uar/core/executor.py` — _coalesce_key initialization
2. `uar/memory/sqlite_store.py` — DDL commit
3. `uar/api/routers/burn_in.py` — Exception logging
4. `tests/api/test_trust_spine_fixes.py` — 3 new regression tests

---

# Post-Review Bug Fixes — Batch 6 (2026-05-31 Continuation)

## Summary

Fixed 3 additional issues identified during comprehensive code review of working changes.

## Fixes

### 1. replay_confidence.py — Explicit Severity for artifact_missing

**File:** `uar/core/replay_confidence.py`
**Line:** 229-233

**Problem:** The `artifact_missing` warning relied on the dataclass default severity ("warning"). This was fragile — if the default changed, the intended severity would change too.

**Fix:** Added explicit `severity="warning"` to document the intentional choice:
```python
warnings.append(ReplayConfidenceWarning(
    "artifact_missing",
    "No outputs, final context, or UOR provenance found",
    "warning",  # Explicit severity
))
```

**Test:** `test_artifact_missing_warning_has_explicit_severity` — Source inspection verifying explicit severity.

---

### 2. burn_in.py — Callable Check for get_metadata

**File:** `uar/api/routers/burn_in.py`
**Line:** 71-74

**Problem:** `BurnInProxy.from_latest()` only checked `hasattr(store, "get_metadata")` but didn't verify it was callable. A malformed store could cause `TypeError` later during the call.

**Fix:** Added callable validation:
```python
if not callable(getattr(store, "get_metadata", None)):
    raise TypeError("store.get_metadata must be callable")
```

**Tests:** 
- `test_burnin_proxy_from_latest_rejects_non_callable_get_metadata` — Verifies TypeError raised
- `test_burnin_proxy_from_latest_accepts_valid_store` — Verifies valid stores work

---

### 3. replay_explorer.py — Exception Logging

**File:** `uar/api/routers/replay_explorer.py`
**Lines:** 99-105, 110-114

**Problem:** `timeline_from_record()` and `score_replay()` failures were silently swallowed with bare `except Exception: pass` patterns. This made debugging difficult.

**Fix:** 
- Moved `logging` import to module level with `logger = logging.getLogger(__name__)`
- Added warning logs for both failure cases:
```python
except Exception as exc:
    logger.warning("timeline_from_record failed for run %s: %s", run_id, exc)
    timeline = {}
```

**Tests:**
- `test_replay_explorer_logs_timeline_failure` — Verifies timeline errors are logged
- `test_replay_explorer_logs_score_failure` — Verifies score errors are logged

---

## Test Results

```
tests/api/test_trust_spine_fixes.py::test_artifact_missing_warning_has_explicit_severity PASSED
tests/api/test_trust_spine_fixes.py::test_burnin_proxy_from_latest_rejects_non_callable_get_metadata PASSED
tests/api/test_trust_spine_fixes.py::test_burnin_proxy_from_latest_accepts_valid_store PASSED
tests/api/test_trust_spine_fixes.py::test_replay_explorer_logs_timeline_failure PASSED
tests/api/test_trust_spine_fixes.py::test_replay_explorer_logs_score_failure PASSED

Full suite: 3775+ passed, 13 skipped, 1 pre-existing YOLO failure
```

## Files Modified (Batch 6)

1. `uar/core/replay_confidence.py` — Explicit severity
2. `uar/api/routers/burn_in.py` — Callable validation
3. `uar/api/routers/replay_explorer.py` — Exception logging
4. `tests/api/test_trust_spine_fixes.py` — 5 new regression tests
