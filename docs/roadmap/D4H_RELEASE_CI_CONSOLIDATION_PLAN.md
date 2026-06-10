# D4H Release CI Consolidation Plan

## Status

D4H opens after D4G CI regression gates are verified.

## Goal

Consolidate release validation so operators know exactly which gates are authoritative.

## Source Gates

- D4D final validation closure
- D4E repeatable runtime smoke
- D4F CI runtime smoke
- D4G CI regression gates

## Tasks

1. Mark `v1.2.8-d4g-ci-verified` as the authoritative D4G tag.
2. Update release validation summary with D4F/D4G CI evidence.
3. Add a single release validation checklist for operators.
4. Document premature/superseded tags without deleting history.
5. Define the next product lane after validation hardening.

## Guardrails

- Do not weaken warning gates.
- Do not make Docker mandatory while daemon availability is unstable.
- Do not add new runtime features during consolidation.
- Keep evidence, tags, workflows, and operator docs aligned.
