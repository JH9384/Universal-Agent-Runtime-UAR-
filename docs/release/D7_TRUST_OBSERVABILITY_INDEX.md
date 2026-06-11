# D7 Trust Observability Release Index

## Baseline

Previous baseline:

- `v1.3.0` — operator-loop baseline

## D7 purpose

D7 makes trust movement visible to operators.

## Release principle

Observe first. Change behavior later only after certification.

## Active documents

- `docs/operations/D7_TRUST_OBSERVABILITY_PLAN.md`
- `docs/certification/D7_TRUST_OBSERVABILITY_OPENING.md`

## Initial scope

Read-only trust observability over:

- recommendation outcomes
- linked runs
- Evidence Pack references
- trust summaries
- recurrence after outcome capture

## Current phase

D7A — opening pack.

## D7H — Trust Movement Preview Contract Certification

- Tag: `v1.3.8-d7h-trust-movement-preview-certification`
- Commit: `d8dfc96`
- Evidence: `docs/certification/D7H_TRUST_MOVEMENT_PREVIEW_CONTRACT.md`

### Certified path

`Mission Control signal → Replay Explorer → Evidence Pack preview → Outcome handoff → Trust movement preview`

### Validation

- `ruff check .`
- `pytest tests/api/test_recommendations.py -q`
- `npm --prefix apps/web test -- TrustMovementPreview --run`
- `npm --prefix apps/web test -- Dashboard --run`
- `npm --prefix apps/web test -- RecommendationOutcomeCapture --run`
- `npm --prefix apps/web test -- ReplayExplorer --run`

### Guardrails

- Read-only trust movement preview.
- Outcome capture still uses the existing recommendation outcome endpoint.
- No trust algorithm change.
- No parallel outcome path.
- No second trust score.
