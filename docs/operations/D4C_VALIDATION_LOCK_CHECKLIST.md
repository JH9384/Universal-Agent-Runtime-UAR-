# D4C Validation Lock Checklist

> Status: ready for validation  
> Scope: D4C fleet/operator/recurrence/evidence spine

---

## Purpose

This checklist defines the stop/go criteria before any further D4C feature expansion.

The current D4C spine is:

```text
Fleet Signal Spine → Operator Loop → Incident Recurrence → Evidence Preview
```

---

## Required Validation

Run one of:

```bash
make validate-d4c
```

or:

```bash
bash scripts/validate_d4c_operator_loop.sh
```

The gate must pass before moving to export/runbook polish.

---

## Validation Coverage

The gate covers:

- fleet signal construction,
- fleet alert surfacing,
- replay linkage,
- recommendation linkage,
- outcome capture,
- trust movement,
- incident recurrence detection,
- incident evidence section,
- Evidence Pack v2 composition,
- Briefing panel,
- Focus panel,
- recurrence summary component,
- Artifacts evidence preview,
- Dashboard replay handoffs,
- frontend production build.

---

## Stop Conditions

Stop and fix if any of the following occur:

- backend D4C tests fail,
- frontend D4C tests fail,
- frontend production build fails,
- Mission Control no longer exposes `fleet_summary`,
- Mission Control no longer exposes `incident_summary`,
- outcome capture stops using `/api/uar/recommendations/outcome`,
- evidence preview stops reusing the Artifacts tab,
- any new incident store or incident console appears without explicit approval.

---

## Go Conditions

Proceed only when:

- `make validate-d4c` passes,
- CI D4C workflow passes or local validation is documented,
- anti-sprawl constraints remain intact,
- docs reflect the current operator path.

---

## Current Boundary

Next eligible work after validation:

1. Evidence Pack export polish,
2. compact recurrence runbook text,
3. CI artifact capture for evidence previews.

Do not start:

- incident workbench,
- plugin registry,
- new dashboard,
- new fleet or incident store,
- second trust score.
