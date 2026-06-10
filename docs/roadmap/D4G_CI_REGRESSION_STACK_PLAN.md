# D4G CI Regression Stack Plan

## Status

D4G is the CI regression-gate lane after D4F CI runtime smoke passed.

## Source Evidence

- D4D final validation closed and tagged.
- D4E runtime smoke is repeatable locally.
- D4F CI runtime smoke passed on GitHub Actions.
- CI Python compatibility decision: use Python `3.12` because package metadata requires `<3.13,>=3.10`.

## Goal

Promote the warning-clean local validation rings into CI-visible regression gates.

## Candidate CI Jobs

1. `ruff check .`
2. `pytest tests/unit` with strict warning gates
3. `pytest tests/api` with strict warning gates
4. `pytest tests/integration` with strict warning gates
5. artifact upload on failure

## Proposed Runtime

- GitHub Actions Python: `3.12`
- Local D4D/D4E evidence remains recorded against Python `3.14.5`.

## Guardrails

- Keep jobs separate so failures are readable.
- Do not make Docker a hard requirement.
- Preserve strict warning gates.
- Do not widen runtime features during D4G.
