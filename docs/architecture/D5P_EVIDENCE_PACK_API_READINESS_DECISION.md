# D5P Evidence Pack API Readiness Decision

## Status

D5P records the API readiness decision after Evidence Pack v2 operator workflow stabilization.

## Decision

Evidence Pack v2 is ready for API design, but not yet ready for API implementation.

## Reason

The local/operator workflow is now stable enough to define an API contract, but the implementation should wait until the contract, security model, and read-only guarantees are fully specified.

## Evidence Foundation

- D5E: read-only core builder exists and is tested.
- D5F: sample renderer exists.
- D5G: JSON-input CLI command exists.
- D5H: live capture script exists and was validated.
- D5I: Makefile target exists.
- D5J: artifact hygiene documented.
- D5K: Make capture validation recorded.
- D5L: promotion template documented.
- D5M: promoted artifact smoke completed and final authority recorded.
- D5N: promotion index exists.
- D5O: operator README exists.

## Proposed API Direction

Potential endpoint:

```text
GET /api/uar/evidence-pack/{run_id}
```

Potential query parameters:

```text
include_markdown=true|false
include_unavailable=true|false
recommendation_id=<id>
outcome_id=<id>
signal_id=<id>
```

## Required API Guardrails

The endpoint must be:

- authenticated,
- read-only,
- non-mutating,
- explicit about missing data,
- tied to run identity,
- backed by the D5E core builder,
- covered by API tests,
- excluded from creating outcomes or trust movement.

## Non-Goals

The API must not:

- create outcomes,
- update trust,
- trigger burn-in,
- trigger replay reconstruction side effects,
- change certification state,
- promote artifacts automatically,
- expose secrets or raw credentials.

## Required Before Implementation

1. Define API response schema.
2. Define auth behavior and permission level.
3. Define missing-data response behavior.
4. Define markdown rendering behavior.
5. Define tests before wiring the router.
6. Decide whether live capture scripts remain separate from the API.

## Recommendation

Proceed to D5Q: Evidence Pack API Contract, then D5R: API Tests, then D5S: Router Implementation.

Do not implement the API directly in D5P.

## Guardrails

- Preserve the local/operator workflow.
- Keep D5E builder read-only.
- Do not weaken D4G warning gates.
- Do not promote artifacts automatically through API calls.
