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

## Result Capture

After running validation, create a result stub:

```bash
make d4c-result
```

This writes a timestamped markdown file under:

```text
docs/operations/validation-results/
```

Then edit the generated file to mark PASS/FAIL and capture any failures or follow-up actions.

### CI artifact capture

The D4C GitHub Actions workflow also uploads a validation log artifact:

```text
d4c-validation-${{ github.run_id }}
```

It contains:

```text
validation.log
```

Retention is 14 days.

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
- Evidence Pack markdown download,
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

The export/runbook/artifact support layer is now in place.

Next eligible work after validation:

1. run focused validation and record result,
2. fix any failures,
3. only then consider broader release hygiene.

Do not start:

- incident workbench,
- plugin registry,
- new dashboard,
- new fleet or incident store,
- second trust score.
