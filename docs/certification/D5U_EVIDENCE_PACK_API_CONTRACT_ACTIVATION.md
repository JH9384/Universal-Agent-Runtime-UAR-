# D5U Evidence Pack API Contract Activation

## Status

D5U converts the D5R skipped Evidence Pack API contract scaffold into active API coverage.

## Purpose

Turn the D5Q contract from documentation and skipped scaffold tests into live regression protection after D5S/D5T router implementation and auth alignment.

## Test File

`tests/api/test_evidence_pack_api_contract.py`

## Activated Coverage

- Unauthenticated requests return `401`.
- Authenticated requests return the Evidence Pack v2 response envelope.
- All canonical sections preserve the availability contract.
- Markdown rendering is optional and explicit.
- Missing evidence remains section-local, not an API failure.
- Empty run IDs return `422`.
- Response payload does not report outcome creation, trust update, or artifact promotion.

## Validation

- `ruff check .`
- `pytest tests/api/test_evidence_pack_api_contract.py -q`
- `pytest tests/api/test_evidence_pack_router.py -q`
- `pytest tests/core/test_evidence_pack.py -q`

## Operational Meaning

Evidence Pack v2 now has active contract coverage across core builder behavior, focused router behavior, and API contract expectations.

## Guardrails

- Do not re-skip these tests without documenting the regression reason.
- Do not add artifact writes through the API.
- Do not mutate outcomes, trust, runs, replay, burn-in, or certification from the evidence-pack endpoint.
