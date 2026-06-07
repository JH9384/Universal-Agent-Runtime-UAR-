# D4C Operator Loop Validation

> Status: active validation gate  
> Date: 2026-06-07  
> Scope: reuse-first fleet operations and operator daily loop

---

## Purpose

This document captures the validation gate for the D4C reuse-first operator loop.

The goal is to prove the operational loop works without creating sprawl:

```text
Briefing → Fleet Health → Top Signal → Replay → Recommendation/Outcome Context → Evidence
```

This validation gate is intentionally focused. It does not replace the full test suite; it protects the new D4C spine while the broader platform continues to evolve.

---

## What Is Covered

### Backend

The backend slice validates:

- fleet signal construction,
- fleet alert adaptation,
- replay / incident / recommendation linkage,
- fleet-linked outcome movement through the existing trust engine,
- fleet evidence section generation,
- Evidence Pack v2 composition,
- operator daily briefing composition,
- Mission Control fleet summary and linkage.

### Frontend

The frontend slice validates:

- AlertBanner fleet surfacing,
- OperatorBriefingPanel rendering and actions,
- Dashboard Briefing → Replay handoff,
- ReplayExplorer initial run filtering,
- frontend production build.

---

## Local Validation

Run from repository root:

```bash
bash scripts/validate_d4c_operator_loop.sh
```

The script runs the focused backend regression tests, the D4C frontend tests, and the frontend production build.

---

## CI Validation

The GitHub Actions workflow is:

```text
.github/workflows/d4c-operator-loop.yml
```

It runs when D4C/operator-loop paths change on pull requests or pushes to `main`. It can also be triggered manually with `workflow_dispatch`.

---

## Anti-Sprawl Rules

The validation gate protects the following constraints:

- no new dashboard app,
- no new fleet store,
- no new briefing store,
- no new replay surface,
- no new incident workbench,
- no new outcome table,
- no second trust score,
- no duplicate alert system,
- no parallel evidence-report pipeline.

If future work violates one of these constraints, it should be reshaped before merge.

---

## Current Reuse Spine

| Step | Reused surface |
|------|----------------|
| Briefing | Existing Dashboard shell |
| Fleet Health | Mission Control `fleet_summary` |
| Top Signal | Fleet signal builder + AlertBanner |
| Replay | Existing ReplayExplorer |
| Incident context | Existing incident IDs from run metadata |
| Recommendation context | Existing recommendation IDs and metadata |
| Outcome movement | Existing recommendation outcome + trust engine |
| Evidence | Evidence Pack v2 composer and fleet evidence section |

---

## Promotion Rule

Before adding another D4C operator feature, this gate should pass locally or in CI.

Recommended command:

```bash
bash scripts/validate_d4c_operator_loop.sh
```

If the gate fails, fix the regression before expanding the operator loop.

---

## Next Eligible Work After Passing

After this gate passes, the next reuse-first work can proceed in one of three directions:

1. **Outcome capture UI** — expose existing recommendation outcome capture inside the operator loop.
2. **Boring Mode** — simplify the daily view into only broken/changed/evidence/action/history/confidence.
3. **Evidence Pack surfacing** — make Evidence Pack v2 visible from the existing Artifacts tab.

Do not start a plugin registry, separate fleet console, or new incident system until the operator loop is validated and stable.
