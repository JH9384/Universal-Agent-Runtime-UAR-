# D4J Entity Retention UI Evidence

## Purpose

D4J surfaces operator metadata retention and integrity directly in Mission Control UI.

## What changed

- Mission Control UI now accepts `entity_retention` and `entity_integrity`.
- A compact Entity Retention card displays:
  - snapshot retention capability
  - entity integrity status
  - snapshot count
  - issue count
  - discovery mode

## Operational meaning

Operators can now see whether snapshot retention is enforceable and whether operator metadata entities are structurally healthy from the primary dashboard.

## Guardrails

- UI treats missing entity-retention data as unknown rather than failing.
- No new backend write path was added.
- No storage behavior changed in this phase.
