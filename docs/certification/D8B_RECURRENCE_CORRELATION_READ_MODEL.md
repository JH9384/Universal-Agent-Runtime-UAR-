# D8B Recurrence Correlation Read Model Certification

## Status

D8B certifies the recurrence correlation preview read model.

## Baseline

- Trust-observability baseline: `v1.4.0`
- D8 opening tag: `v1.4.1-d8a-trust-recurrence-correlation-opening`
- Normalized plan tag: `v1.4.2-d8a-trust-recurrence-plan-normalized`

## Certified path

```text
Mission Control signal
→ Replay Explorer
→ Evidence Pack preview
→ Outcome handoff
→ Trust movement preview
→ Recurrence correlation preview
```

## What D8B adds

D8B adds a read-only recurrence correlation preview over existing operator evidence linkage.

The preview answers:

`After an outcome and trust movement were observed, did the same recommendation/run linkage show later recurrence?`

## Read model fields

- `recommendation_id`
- `run_id`
- `outcome_type`
- `evidence_refs`
- `trust_delta`
- `later_recurrence_count`
- `later_recurrence_run_ids`
- `correlation_status`

## Guardrails

- No trust algorithm change.
- No recommendation ranking change.
- No new outcome path.
- No duplicate incident or recurrence store.
- No mutation from the recurrence correlation preview.
- No second trust score.
- No parallel evidence pipeline.

## Validation

Validated locally:

```text
ruff check .
pytest tests/api/test_recommendations.py -q
npm --prefix apps/web test -- RecurrenceCorrelationPreview --run
npm --prefix apps/web test -- TrustMovementPreview --run
npm --prefix apps/web test -- Dashboard --run
npm --prefix apps/web test -- RecommendationOutcomeCapture --run
npm --prefix apps/web test -- ArtifactBrowser --run
npm --prefix apps/web test -- OperatorBriefingPanel --run
npm --prefix apps/web test -- FocusModePanel --run
npm --prefix apps/web test -- ReplayExplorer --run
```

## Operational meaning

Operators can now see whether the observed trust movement and recorded recommendation outcome were followed by later recurrence, without leaving the governed replay/evidence/outcome path.
