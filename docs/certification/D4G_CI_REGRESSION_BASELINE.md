# D4G CI Regression Baseline

## Status

D4G CI regression gates passed.

## Date

2026-06-09

## Workflow

`.github/workflows/d4g-regression.yml`

## CI Runtime

- Python: `3.12`
- Reason: UAR package metadata currently requires `<3.13,>=3.10`.

## Gates

- Lint: `ruff check .`
- Unit warning-clean suite
- API warning-clean suite
- Integration warning-clean suite

## Operational Meaning

D4G promotes the local D4D warning-clean validation stack into CI-visible regression gates.

## Guardrails

- Jobs remain separated for readable failures.
- Docker remains outside this gate.
- Strict warning gates remain active.
- No production runtime behavior is changed by this evidence record.
