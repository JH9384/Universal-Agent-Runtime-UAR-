# D4G Entity Retention Mission Control Evidence

## Purpose

D4G surfaces operator metadata entity-retention health inside Mission Control.

## What changed

- `/api/uar/mission-control` now includes `entity_retention`.
- `/api/uar/operator/entity-health` remains the direct diagnostic endpoint.
- Mission Control UI renders a compact Entity Retention card.

## Operational meaning

Operators can now see whether snapshot retention is fully enforceable from the primary control loop instead of relying only on implementation knowledge.

## Guardrails

- Entity-retention health failure degrades into a warning payload.
- Snapshot retention remains safe no-op when complete listing or real deletion is unavailable.
- No new storage behavior was added in this phase.
