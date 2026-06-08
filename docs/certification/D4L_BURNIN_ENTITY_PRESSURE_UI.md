# D4L Burn-In Entity Pressure UI Evidence

## Purpose

D4L exposes D4K entity-retention pressure fields in the operator-facing burn-in UI.

## What changed

Burn-in UI now displays:

- Retention capable rate
- Final entity integrity status
- Entity integrity issue count start/end
- Max entity integrity issue count
- Entity snapshot count start/end

## Operational meaning

Operators can now see whether metadata retention and integrity remain stable over burn-in windows without reading raw JSON reports.

## Guardrails

- Missing D4K fields render as unknown/blank values.
- No backend write path was added.
- No storage behavior changed.
