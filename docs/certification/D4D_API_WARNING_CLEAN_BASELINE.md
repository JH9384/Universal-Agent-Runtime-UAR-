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
cd "/Volumes/Sabrent SSD/Projects/Universal-Agent-Runtime-UAR-"

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

The API validation ring requires a higher file descriptor limit than the default local shell value of `256`.

Use `ulimit -n 8192` before running the API suite locally.

## Guardrails

- No production runtime behavior is changed by this evidence record.
- This document records validation scope only.
- Strict warning gates remain active for D4D validation.
