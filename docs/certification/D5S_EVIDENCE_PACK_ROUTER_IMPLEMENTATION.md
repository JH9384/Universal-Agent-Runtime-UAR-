# D5S Evidence Pack Router Implementation

## Status

D5S adds the first read-only Evidence Pack v2 API router implementation.

## Endpoint

`GET /api/uar/evidence-pack/{run_id}`

## Router

`uar/api/routers/evidence_pack.py`

## Aggregation

The router is included through:

`uar/api/routers/__init__.py`

## Implemented Behavior

- Returns Evidence Pack v2 response envelope.
- Uses the D5E core builder.
- Supports optional Markdown rendering through `include_markdown=true`.
- Supports hiding unavailable sections through `include_unavailable=false`.
- Rejects empty run IDs with `422`.
- Does not write artifacts.
- Does not mutate outcomes, trust, runs, replay, burn-in, or certification.

## Validation

- `ruff check .` passed
- `pytest tests/api/test_evidence_pack_router.py -q` passed: `4 passed`
- `pytest tests/core/test_evidence_pack.py -q` passed: `6 passed`

## Guardrails

- D5R scaffold tests remain skipped until the full auth contract is wired.
- Router remains read-only.
- No artifact promotion occurs through the API.
- Source data wiring can be expanded later without changing the core Evidence Pack v2 shape.
