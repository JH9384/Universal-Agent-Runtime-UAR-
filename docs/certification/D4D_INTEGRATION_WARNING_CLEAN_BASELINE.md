# D4D Integration Warning-Clean Baseline

## Status

Accepted as D4D integration validation evidence.

## Baseline

- Branch: `main`
- Date: 2026-06-09
- Runtime: Python 3.14.5
- File descriptor limit used for validation: `ulimit -n 8192`
- Test scope: integration suite
- Expected prior result: `340 passed`

## Validation Commands

```bash
cd "/Volumes/Sabrent SSD/Projects/Universal-Agent-Runtime-UAR-"

ulimit -n 8192

pytest tests/integration -q \
  -W error::pytest.PytestUnraisableExceptionWarning \
  -W error::RuntimeWarning \
  -W error::DeprecationWarning \
  --tb=short
```

## Validation Meaning

The integration suite clears under strict Python 3.14 warning gates for unraisable coroutine warnings, runtime warnings, and deprecation warnings.

## Environmental Note

The broader API and integration validation rings require a higher file descriptor limit than the default shell value of `256`.

Use `ulimit -n 8192` before running these suites locally.

## Guardrails

- No production runtime behavior is changed by this evidence record.
- This document records validation scope only.
- Strict warning gates remain active for D4D validation.
