# D4D Warning-Clean Validation Index

## Status

D4D warning-clean validation evidence is captured across unit, API, and integration rings.

## Evidence Stack

| Ring | Scope | Result | Evidence |
| --- | --- | ---: | --- |
| Unit | `tests/unit` | `1649 passed` | `D4D_PYTHON_314_WARNING_CLEAN_BASELINE.md` |
| API | `tests/api` | `783 passed, 1 skipped` | `D4D_API_WARNING_CLEAN_BASELINE.md` |
| Integration | `tests/integration` | `340 passed` | `D4D_INTEGRATION_WARNING_CLEAN_BASELINE.md` |

## Runtime

- Python: `3.14.5`
- Date: `2026-06-09`
- Local API/integration file descriptor requirement: `ulimit -n 8192`

## Strict Warning Gates

The validation rings were run with warnings escalated for:

- `pytest.PytestUnraisableExceptionWarning`
- `RuntimeWarning`
- `DeprecationWarning`
- `UserWarning` for unit validation

## Operational Meaning

The Python 3.14 validation pass proves that the core local test rings can run without hidden coroutine cleanup failures, unraisable teardown noise, or deprecated test-client behavior blocking D4D evidence collection.

## Next Validation Layer

The next validation layer should move outward from clean test execution into runtime evidence:

1. Mission Control smoke checks
2. burn-in replay evidence
3. runtime soak validation
4. artifact export verification
5. release-gate summary refresh

## Guardrails

- This index records validation evidence only.
- No runtime production behavior is changed by this document.
- Strict warning gates should remain active for D4D validation.
