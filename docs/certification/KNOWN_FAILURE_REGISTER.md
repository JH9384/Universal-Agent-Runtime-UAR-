# Known Failure Register

**Repository:** Universal Agent Runtime (UAR)  
**Date:** 2026-06-01  
**Certified Baseline:** `omega-2-certified` / `release/omega-2-certified`  

---

## Register

| ID | Test | Class | Severity | Action | Root Cause |
|----|------|-------|----------|--------|------------|
| F1 | `test_docs_browse_anonymous_dev` | Environment | Low | Fix `.env` or patch test fixture | `.env` contains placeholder `PROJECT_ROOT=/path/to/project` |
| F2 | `test_docs_browse_recursive_anonymous_dev` | Environment | Low | Fix `.env` or patch test fixture | Same as F1 |
| F3 | `test_docs_browse_authenticated_dev` | Environment | Low | Fix `.env` or patch test fixture | Same as F1 |
| F4 | `test_docs_read_only_work_with_auth_prod` | Environment | Low | Fix `.env` or patch test fixture | Same as F1 |

---

## Classification

**Type:** Environment configuration issue  
**Impact:** 4 test failures, all isolated to `docs/browse` endpoint  
**Runtime impact:** None — the endpoint works correctly when `PROJECT_ROOT` is valid  
**Certification impact:** None — outside Ω-2 certification scope

---

## Root Cause Analysis

The `.env` file at repository root contains:

```
PROJECT_ROOT=/path/to/project
```

This is a placeholder value from `.env.example` that was never updated.

The `docs_browse` endpoint (`uar/api/routers/docs.py`) resolves user-provided paths relative to `PROJECT_ROOT`:

```python
def _docs_root():
    return Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
```

When `PROJECT_ROOT=/path/to/project`, the resolved path `/path/to/project` does not exist, so the endpoint returns 404 with body:

```json
{"error": "Path not found", "message": "Path not found"}
```

The other docs endpoints (`docs_presets`, `docs_library`) do not fail because:

- `docs_presets` enumerates candidate subdirectories and skips non-existent ones
- `docs_library` creates the library directory with `mkdir(parents=True, exist_ok=True)`

---

## Verification

Setting `PROJECT_ROOT` to the actual repository path makes all 4 tests pass:

```bash
PROJECT_ROOT=/actual/repo/path pytest tests/api/test_auth_modes.py -v
# Result: 22 passed, 0 failed
```

---

## Recommended Fix

**Option A (recommended):** Add a `PROJECT_ROOT` patch to the `dev_env` fixture in `tests/api/test_auth_modes.py`:

```python
@pytest.fixture
def dev_env():
    with patch.dict(os.environ, {
        "ENVIRONMENT": "development",
        "PROJECT_ROOT": str(Path(__file__).resolve().parents[3]),
    }, clear=False):
        yield
```

**Option B:** Update `.env` to use the actual project root. However, this is machine-specific and should not be committed.

**Option C:** Make `docs_browse` fall back to `Path.cwd()` when `PROJECT_ROOT` points to a non-existent path. This is a product decision, not a certification requirement.

---

## Disposition

| Criterion | Assessment |
|-----------|-----------|
| Is this a runtime defect? | **No** — endpoint works correctly with valid `PROJECT_ROOT` |
| Is this a test defect? | **Partially** — test fixtures do not isolate `PROJECT_ROOT` |
| Is this an environment issue? | **Yes** — `.env` placeholder causes test environment mismatch |
| Does this affect certified functionality? | **No** — docs/browse is outside Ω-1/Ω-2 certification scope |
| Should this block Ω-3? | **No** — classification complete, fix is straightforward |

---

## Sign-off

| Role | Assessment |
|------|------------|
| Root cause identified | ✅ |
| Classification assigned | ✅ |
| Fix options documented | ✅ |
| Impact on certification assessed | ✅ (none) |

**Known Failure Register: COMPLETE** 🌊
