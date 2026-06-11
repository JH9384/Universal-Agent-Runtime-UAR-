# D8D Recurrence Correlation Regression Certification

## Status

D8D validates the read-only recurrence correlation layer after D8B/D8C wiring.

## Certified operator path

```text
Mission Control signal
→ Replay Explorer
→ Evidence Pack preview
→ Outcome handoff
→ Trust movement preview
→ Recurrence correlation preview
```

## Guardrails

- Read-only recurrence correlation preview.
- No trust algorithm change.
- No automatic ranking change.
- No second trust score.
- No new outcome path.
- No duplicate incident store.
- No mutation from observability views.

## Validation commands

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

D8 now lets an operator inspect whether a recommendation outcome and trust movement were followed by later recurrence without leaving the governed Mission Control → Replay → Evidence Pack path.
