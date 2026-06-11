# UAR v1.2 D6 Operator Loop Release

## Release theme

D6 closes the operator loop from Mission Control signal detection to replay-backed evidence, recommendation outcome capture, and downstream trust movement.

## Primary operator path

Signal → Replay → Evidence Pack → Outcome → Trust Movement

## Release components

### Evidence Pack access

Replay Explorer now exposes a run-scoped Evidence Pack action.

### Evidence Pack preview

The UI renders a guarded, read-only Evidence Pack markdown preview.

### Recommendation outcome handoff

When recommendation linkage exists, Replay Explorer exposes outcome capture directly from the Evidence Pack preview.

Supported outcome states:

- resolved
- recurred
- unknown

### Linkage propagation

Mission Control briefing and focus replay actions carry linked recommendation IDs into Replay Explorer.

### Regression coverage

Validated paths include:

- Briefing → Replay
- Focus → Replay
- Replay → Artifacts
- Replay → Evidence Pack
- Evidence Pack → Outcome handoff
- Outcome handoff → recommendation outcome POST
- Missing recommendation linkage → guarded warning

## Guardrails

- No new persistence model.
- No parallel operator-outcome table.
- No alternate trust path.
- No fleet-specific outcome fork.
- Evidence Pack preview remains read-only.
- Outcome recording reuses existing `/api/uar/recommendations/outcome`.

## Release tags

- v1.2.47-d6a-replay-evidence-pack-action
- v1.2.48-d6b-replay-evidence-pack-action-wired
- v1.2.49-d6c-replay-evidence-pack-ui-test
- v1.2.50-d6d-replay-evidence-pack-preview-stable
- v1.2.51-d6e-replay-evidence-pack-state-hardened
- v1.2.51-d6f-replay-evidence-pack-preview-stable
- v1.2.52-d6g-guarded-replay-outcome-handoff
- v1.2.53-d6g-replay-recommendation-linkage
- v1.2.54-d6h-replay-outcome-linkage-regression
- v1.2.55-d6i-replay-outcome-post-regression
- v1.2.56-d6j-replay-outcome-handoff-docs
- v1.2.57-d6k-replay-outcome-certification

## Operational meaning

D6 makes Mission Control operationally closed. A signal can now become inspected evidence, an operator decision, and trust-learning input without leaving the governed runtime surface.
