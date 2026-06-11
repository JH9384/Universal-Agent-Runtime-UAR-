# D6 Replay Evidence Outcome Handoff

## Status

Active and validated.

## Purpose

D6 closes the operator loop from Mission Control signal review into replay inspection, Evidence Pack preview, and recommendation outcome capture.

## Operator loop

Signal → Replay → Evidence Pack → Outcome → Trust Movement

## Implemented behavior

- Mission Control briefing and focus replay actions can carry linked recommendation IDs.
- Dashboard preserves the replay run ID and linked recommendation IDs while switching into Replay Explorer.
- Replay Explorer can open a read-only Evidence Pack v2 preview for the selected run.
- If linked recommendation IDs are present, Replay Explorer renders the existing recommendation outcome capture control.
- If no recommendation linkage is available, Replay Explorer shows a guarded warning instead of inventing or requiring a recommendation ID.
- Outcome capture reuses the existing POST `/api/uar/recommendations/outcome` path.
- No new outcome table, persistence model, or fleet-specific outcome endpoint was added.

## Guardrails

- Evidence Pack preview is read-only.
- Outcome recording remains recommendation-scoped.
- Run linkage is passed through as evidence context.
- Missing recommendation linkage blocks outcome capture and explains why.
- Replay Explorer does not create recommendation IDs.
- Mission Control remains the authority for signal, replay, evidence, recommendation, and outcome routing.

## Regression coverage

Validated paths:

- Dashboard briefing → Replay tab with run filter.
- Dashboard focus → Replay tab with run filter.
- Replay detail → Artifact evidence reference.
- Replay detail → Evidence Pack preview.
- Briefing replay → recommendation linkage carried into Replay Explorer.
- Replay Evidence Pack handoff → recommendation outcome POST.
- OperatorBriefingPanel replay callback carries recommendation IDs.
- FocusModePanel replay callback carries recommendation IDs.

## Operational meaning

An operator can now start from a Mission Control signal, inspect the run, open the Evidence Pack, and record whether the linked recommendation resolved, recurred, or remains unknown. That result feeds the existing trust-learning path without creating a parallel operator outcome system.
