# D4D Python 3.14 Warning-Clean Unit Baseline

## Status

Accepted as D4D validation evidence.

## Baseline

- Branch: `main`
- Commit: `246ee85`
- Date: 2026-06-09
- Runtime: Python 3.14.5
- Test scope: unit suite
- Result: `1649 passed`

## Validation Commands

    ruff check .

    pytest tests/unit -q \
      -W error::pytest.PytestUnraisableExceptionWarning \
      -W error::RuntimeWarning \
      -W error::UserWarning \
      -W error::DeprecationWarning

## Evidence

    All checks passed!
    1649 passed in 36.64s

## What This Proves

The UAR unit suite is now clean under strict Python 3.14 warning pressure.

This validates:

- no unawaited coroutine leaks in the hardened unit paths
- no pytest unraisable coroutine teardown failures
- no runtime-warning regressions
- no user-warning leakage under strict mode
- no deprecation-warning leakage under strict mode
- middleware tests updated away from deprecated httpx data= raw-body usage
- third-party socket and chromadb warning handling centralized through pytest configuration

## Operational Meaning

This is now a safe unit-level baseline for D4D burn-in expansion.

The next validation layer should move outward from unit scope into:

1. focused integration tests
2. API route tests
3. Mission Control smoke checks
4. burn-in evidence replay
5. runtime soak validation

## Guardrails

- No production runtime behavior was intentionally changed.
- Test hardening was limited to deterministic cleanup, warning control, and deprecated test-client usage.
- Third-party warnings are filtered only where they are environmental/test-harness noise.
- The strict warning gate should remain active for D4D validation.
