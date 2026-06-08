# D4M Entity Pressure Alerts Evidence

## Purpose

D4M surfaces operator entity-retention and integrity pressure through the existing alert-summary path.

## What changed

`GET /api/uar/alerts/summary` now emits alert candidates for:

- failed operator entity integrity
- warning-level operator entity integrity
- nonzero operator entity issue counts
- snapshot retention that is not fully enforceable

## Operational meaning

Operators no longer need to manually inspect Mission Control details to know that metadata integrity or retention has degraded. Entity pressure now participates in the same alert banner flow as fleet, burn-in, certification, and runtime warnings.

## Guardrails

- No new alert endpoint was created.
- No new persistence model was introduced.
- Alerts reuse the existing `entity_pressure` source and `health` tab routing.
- Missing entity-retention or entity-integrity payloads produce no alert.
