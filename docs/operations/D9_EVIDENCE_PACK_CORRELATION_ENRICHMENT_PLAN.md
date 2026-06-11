# D9 Evidence Pack Correlation Enrichment Plan

## Status

D9 opens after the `v1.5.0` recurrence-correlation observability baseline.

## Purpose

D8 made recurrence correlation visible in the governed operator path. D9 enriches Evidence Pack output so that the same correlation context can travel with exported/reviewable evidence.

## Core question

Can an Evidence Pack show not only what happened, but whether the operator outcome and trust movement reduced later recurrence?

## Scope

D9 is read-only enrichment over existing data:

- run evidence
- recommendation outcome linkage
- trust movement preview
- recurrence correlation preview
- Evidence Pack markdown
- Evidence Pack API response shape

## Non-goals

- No new trust algorithm.
- No automatic ranking change.
- No second trust score.
- No duplicate incident store.
- No new outcome path.
- No Evidence Pack mutation side effects.

## Target path

```text
Mission Control signal
→ Replay Explorer
→ Evidence Pack preview
→ Outcome handoff
→ Trust movement preview
→ Recurrence correlation preview
→ Evidence Pack correlation section
```

## D9 slices

### D9A — Opening plan

Document D9 scope, guardrails, and reuse boundaries.

### D9B — Evidence Pack field map

Map correlation fields to existing sources without inventing data.

### D9C — Markdown section

Add a read-only recurrence-correlation section to Evidence Pack markdown when data exists.

### D9D — API response enrichment

Expose correlation context in the Evidence Pack API response as an optional section.

### D9E — UI preview validation

Verify Replay Explorer displays the enriched section without changing outcome or trust behavior.

### D9F — Certification

Capture validation evidence and freeze D9 as the Evidence Pack correlation enrichment baseline.

## Success condition

An exported Evidence Pack can answer:

`What evidence supported the operator action, how did trust move, and did recurrence later improve?`

without requiring a separate report pipeline.
