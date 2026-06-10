# D5T Evidence Pack API Auth Alignment

## Status

D5T aligns the Evidence Pack v2 API router with existing UAR API authentication behavior.

## Endpoint

`GET /api/uar/evidence-pack/{run_id}`

## Auth Behavior

The endpoint now requires authenticated API access using the existing UAR auth middleware pattern.

Unauthenticated requests return `401` with an authentication-required error payload.

## Implementation Detail

The router uses:

- `HTTPBearer(auto_error=False)`
- `auth_middleware(credentials)`
- explicit `401` rejection when user info is absent

## Validation

- `ruff check .` passed
- `pytest tests/api/test_evidence_pack_router.py -q` passed
- `pytest tests/core/test_evidence_pack.py -q` passed

## Implemented Guardrails

- Unauthenticated requests are rejected.
- Authenticated requests can generate read-only evidence pack responses.
- Evidence pack generation does not write artifacts.
- Evidence pack generation does not mutate outcomes, trust, runs, replay, burn-in, or certification.

## Operational Meaning

The Evidence Pack v2 API is now closer to the D5Q contract: router behavior remains read-only while access is protected by the existing API auth layer.

## Guardrails

- Do not add artifact promotion to this endpoint.
- Do not weaken D4G warning gates.
- Keep local/operator evidence-pack scripts as first-class workflows.
