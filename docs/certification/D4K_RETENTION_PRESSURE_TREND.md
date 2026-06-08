# D4K Retention Pressure Trend Evidence

## Purpose

D4K turns operator entity-retention and integrity state into long-duration burn-in evidence.

## What changed

The long-duration burn-in probe now samples Mission Control for:

- `entity_retention_capable`
- `entity_retention_snapshot_count`
- `entity_integrity_status`
- `entity_integrity_issue_count`

The burn-in summary now reports retention capability rate, snapshot count start/end, final integrity status, and issue count start/end.

## Operational meaning

Snapshot retention and metadata integrity are no longer only static endpoint or UI facts. They are trendable operational signals during soak and burn-in runs.

## Guardrails

- Mission Control probe failure records degraded fields instead of failing the burn-in.
- No storage behavior changed.
- No write path was added.
