# Fix Batch 6 — 2026-05-31

## Summary

Fixed pre-existing bug pattern in `postgres_store.py` where `zip(cols, row)` without strict validation could silently drop data when column lists and SELECT statements get out of sync.

## Changes Made

### 1. `uar/memory/postgres_store.py`

**Problem:**

All 4 `zip(cols, row)` calls used `strict=False` (or implicit default), which silently truncates or pads when column count mismatches row field count. This could lead to:

- Silent data loss if SELECT adds columns but `cols` list not updated
- Silent null values if `cols` has more entries than SELECT returns

**Fix:**

Changed all 4 locations to use `strict=True`:

- `list_records()` — line 318
- `get_by_run_id()` — line 363
- `list_records_async()` — line 455
- `get_by_run_id_async()` — line 491

Also fixed line length issue at line 391 (long ternary expression).

**Impact:**

Now raises `ValueError` immediately on column/row length mismatch, failing fast rather than corrupting data.

### 2. `tests/api/test_trust_spine_fixes.py`

**Added regression test:**

`test_postgres_store_zip_uses_strict_true()` — source inspection test verifying:

- All `zip(cols, row)` calls use `strict=True`
- No remaining `strict=False` patterns
- No bare `zip(cols, row)` without strict parameter

## Test Results

```text
3765 passed, 13 skipped, 33 warnings in 72.28s
```

All Trust Spine tests pass:

```text
tests/api/test_trust_spine_fixes.py::test_postgres_store_zip_uses_strict_true PASSED
```

## Files Modified

1. `uar/memory/postgres_store.py` — zip strict=True fix + line length fix
2. `tests/api/test_trust_spine_fixes.py` — regression test added

## Verification

Run targeted tests:

```bash
python -m pytest tests/api/test_trust_spine_fixes.py::test_postgres_store_zip_uses_strict_true -v
python -m pytest tests/test_store_and_contracts.py -v
```

Run full suite (excluding pre-existing YOLO failure):

```bash
python -m pytest tests/ --ignore=tests/bug_patterns --ignore=tests/e2e --ignore=tests/unit/test_new_skills.py -q
```
