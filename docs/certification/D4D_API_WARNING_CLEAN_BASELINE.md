# D4D API Warning-Clean Baseline

## Status

Accepted as D4D API validation evidence.

## Baseline

- Branch: `main`
- Date: 2026-06-09
- Runtime: Python 3.14.5
- File descriptor limit used for validation: `ulimit -n 8192`
- Test scope: API suite
- Result: `783 passed, 1 skipped`

## Validation Commands

```bash
ulimit -n 8192

ruff check .

pytest tests/api -q \
  -W error::pytest.PytestUnraisableExceptionWarning \
  -W error::RuntimeWarning \
  -W error::DeprecationWarning \
  --tb=short
```

## Validation Meaning

The API suite clears under strict Python 3.14 warning gates for unraisable coroutine warnings, runtime warnings, and deprecation warnings.

## Environmental Note

The default shell file descriptor limit of `256` is too low for broader API/integration validation and can produce secondary teardown failures such as `Too many open files`.

For this validation ring, `ulimit -n 8192` is required.

## Guardrails

- No production runtime behavior was changed.
- API warning cleanup was limited to replacing deprecated `httpx` / `TestClient` raw `data=` usage with `content=`.
- Strict warning gates remain active for D4D validation.
