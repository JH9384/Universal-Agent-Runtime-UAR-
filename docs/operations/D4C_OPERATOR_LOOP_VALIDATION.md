# D4C Operator Loop Validation

> Status: active validation gate  
> Date: 2026-06-07  
> Scope: reuse-first fleet operations, operator daily loop, and recurrence surfacing

---

## Purpose

This document captures the validation gate for the D4C reuse-first operator loop.

The current loop is:

```text
Briefing / Focus → Fleet Signal or Recurrence → Replay → Outcome Capture → Evidence Pack Preview
```

This validation gate is intentionally focused. It does not replace the full test suite; it protects the D4C spine while the broader platform continues to evolve.

---

## What Is Covered

### Backend

The backend slice validates:

- fleet signal construction,
- fleet alert adaptation,
- replay / incident / recommendation linkage,
- fleet-linked outcome movement through the existing trust engine,
- fleet evidence section generation,
- incident intelligence recurrence detection,
- incident evidence section generation,
- Evidence Pack v2 composition,
- operator daily briefing composition,
- Mission Control fleet summary, incident summary, and linkage.

### Frontend

The frontend slice validates:

- AlertBanner fleet surfacing,
- OperatorBriefingPanel rendering and actions,
- FocusModePanel rendering and actions,
- IncidentRecurrenceSummary rendering and actions,
- RecommendationOutcomeCapture,
- ArtifactBrowser Evidence Pack preview,
- recurrence-aware Evidence Pack preview,
- Dashboard Briefing → Replay handoff,
- Dashboard Focus → Replay handoff,
- Dashboard recurrence → Replay handoff,
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
- no new incident console,
- no new incident store,
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
| Focus | Existing Dashboard shell |
| Fleet Health | Mission Control `fleet_summary` |
| Recurrence | Mission Control `incident_summary` |
| Top Signal | Fleet signal builder + AlertBanner |
| Replay | Existing ReplayExplorer |
| Incident context | Existing incident IDs from run metadata |
| Recommendation context | Existing recommendation IDs and metadata |
| Outcome movement | Existing recommendation outcome + trust engine |
| Evidence | Evidence Pack v2 composer, fleet section, incident section, Artifacts preview |

---

## Promotion Rule

Before adding another D4C operator feature, this gate should pass locally or in CI.

Recommended command:

```bash
bash scripts/validate_d4c_operator_loop.sh
```

If the gate fails, fix the regression before expanding the operator loop.

---

## Current Boundary

D4C now has a complete reuse-first operator loop through recurrence-aware evidence surfacing.

The next responsible step is validation and cleanup, not a new incident console.

Potential future work after validation:

1. improve export behavior for Evidence Pack v2,
2. add compact operator runbook text for recurring incidents,
3. add CI artifacts for evidence previews,
4. only then consider incident workbench requirements if real operators need it.

Do not start a plugin registry, separate fleet console, or new incident system until the operator loop is validated and stable.
