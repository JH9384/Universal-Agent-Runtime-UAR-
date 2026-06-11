# D8 Trust Recurrence Correlation Plan

## Status

D8 opens after the `v1.4.0` trust-observability baseline.

## Purpose

D7 made trust movement visible. D8 determines whether that movement predicted later recurrence.

## Core question

After an operator records an outcome and trust movement is observed, did the same failure pattern recur later?

## Scope

D8 is read-only observability over existing data:

- recommendation outcomes
- trust movement preview records
- incident recurrence summaries
- run/evidence references
- Mission Control signal linkage

## Non-goals

- No trust algorithm change.
- No automatic ranking change.
- No second trust score.
- No new outcome path.
- No duplicate incident store.
- No mutation from observability views.

## Operator path

```text
Mission Control signal
→ Replay Explorer
→ Evidence Pack preview
→ Outcome handoff
→ Trust movement preview
→ Recurrence correlation preview
```

## D8 slices

### D8A — Opening plan

Document D8 scope, guardrails, and intended reuse paths.

### D8B — Read model

Define a small read-only correlation shape that can represent:

- recommendation ID
- outcome type
- source run
- evidence refs
- trust before/after/delta when available
- later recurrence count
- later recurrence run IDs
- correlation status

### D8C — UI preview

Show recurrence correlation below trust movement preview inside Replay Explorer.

### D8D — Regression coverage

Prove that the full operator path renders correlation context without mutating trust, outcomes, incidents, or evidence.

### D8E — Certification

Capture validation evidence and freeze D8 as a read-only correlation layer.

## Success condition

An operator can answer:

`Did this recommendation outcome and trust movement actually reduce recurrence later?`

without leaving the governed Mission Control → Replay → Evidence Pack path.
