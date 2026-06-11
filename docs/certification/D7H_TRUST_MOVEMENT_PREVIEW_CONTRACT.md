# D7H Trust Movement Preview Contract Certification

## Status

D7H certifies the D7 trust movement preview contract.

## Baseline

- Operator-loop baseline: `v1.3.0`
- Current D7 authority tag: `v1.3.7-d7g-trust-movement-preview-contract`

## Certified path

```text
Mission Control signal
→ Replay Explorer
→ Evidence Pack preview
→ Outcome handoff
→ Trust movement preview
```

## Contract

The trust movement preview is read-only.

It may:

- accept recommendation IDs and an optional run ID
- return trust movement preview records
- show empty or unknown movement safely
- preserve evidence and run linkage
- support UI observability

It must not:

- record an outcome
- recompute trust
- mutate trust scores
- mutate runs
- create a second outcome model
- create a second trust score

## Validated API

```text
POST /api/uar/recommendations/trust-movement/preview
```

## Regression evidence

Validated locally:

```text
ruff check .
pytest tests/api/test_recommendations.py -q
npm --prefix apps/web test -- TrustMovementPreview --run
npm --prefix apps/web test -- Dashboard --run
npm --prefix apps/web test -- RecommendationOutcomeCapture --run
npm --prefix apps/web test -- ReplayExplorer --run
```

## Operational meaning

Operators can now see trust movement context from the same governed path that already handles evidence inspection and recommendation outcome capture.

D7 does not change the learning algorithm. It makes trust movement observable.
