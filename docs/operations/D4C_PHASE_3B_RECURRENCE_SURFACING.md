# D4C Phase 3B — Recurrence Surfacing

> Status: implemented  
> Principle: reuse-first, no incident console

---

## Purpose

Phase 3B surfaces the top recurrence pattern from Mission Control into existing operator views.

The operator path is:

```text
Mission Control incident_summary → Briefing / Focus → Replay → Evidence
```

No new incident dashboard, store, endpoint, or workflow is introduced.

---

## Data Source

The canonical payload is:

```text
/api/uar/mission-control
```

The reused field is:

```text
incident_summary.top_pattern
```

It is built from existing records, outcome rows, recommendation metadata, and the existing trust engine.

---

## Surfaced Fields

Briefing and Focus can show:

- recurrence scope and value,
- recurrence count,
- affected run IDs,
- latest run ID,
- linked incident IDs,
- linked recommendation IDs,
- evidence refs.

The latest run ID can open the existing Replay Explorer.

The Evidence button routes to the existing Artifacts tab.

---

## Components

Frontend reuse component:

```text
apps/web/src/components/mission-control/IncidentRecurrenceSummary.tsx
```

Mounted in:

```text
apps/web/src/components/mission-control/OperatorBriefingPanel.tsx
apps/web/src/components/mission-control/FocusModePanel.tsx
```

---

## Validation

Run:

```bash
bash scripts/validate_d4c_operator_loop.sh
```

Additional coverage includes:

- `IncidentRecurrenceSummary.test.tsx`,
- Briefing recurrence surfacing,
- Focus recurrence surfacing,
- Dashboard recurrence → Replay handoff.

---

## Anti-Sprawl Result

Held clean:

- no incident console,
- no incident store,
- no duplicate endpoint,
- no new dashboard,
- no parallel workflow,
- no second trust score.

---

## Next Eligible Step

After validation, the next responsible step is either:

1. local/CI validation and cleanup, or
2. recurrence-aware Evidence Pack preview in the existing Artifacts tab.

Do not build an incident workbench yet.
