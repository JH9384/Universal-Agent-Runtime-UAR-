# D4I Entity Integrity Mission Control Evidence

## Purpose

D4I wires operator entity integrity into the primary Mission Control snapshot.

## What changed

- `/api/uar/mission-control` now includes `entity_integrity`.
- The direct diagnostic endpoint remains `GET /api/uar/operator/entity-integrity`.
- Mission Control degrades safely if integrity calculation fails.

## Operational meaning

Operators can now inspect metadata retention capability and metadata structural integrity from the main control-loop snapshot.

## Guardrails

- Integrity failures do not break Mission Control.
- No new write path was added.
- No new storage model was introduced.
