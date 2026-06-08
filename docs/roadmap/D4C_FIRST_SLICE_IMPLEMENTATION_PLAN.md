# D4C First Slice Implementation Plan — Reuse-First

> Date: 2026-06-07  
> Arc: Next Development Arc — Reuse-First Operational Control Plane  
> Slice: Fleet Health card → top fleet alert → replay → incident update → outcome capture → trust movement → evidence-pack section

---

## Objective

Implement the smallest complete D4C path that proves UAR can operate as a reusable control plane without creating sprawl.

The first slice should prove this loop:

```text
Fleet signal
  → Mission Control card
  → Top fleet alert
  → Replay Explorer / Incident Workbench
  → Outcome capture
  → Trust or effectiveness movement
  → Evidence Pack v2 section
```

This is not a new dashboard and not a new subsystem. It is a composition of existing primitives.

---

## Reuse Commitments

### Reuse existing backend surfaces

Prefer extending or composing:

- `/api/uar/mission-control`
- `/api/uar/mission-control/alert`
- `/api/uar/replay/{run_id}`
- `/api/uar/incidents`
- `/api/uar/recommendations/outcome`
- `/api/uar/recommendations/trust`
- `/api/uar/recommendations/effectiveness`
- evidence-pack scripts under `scripts/hardening/`

### Reuse existing frontend surfaces

Prefer composing:

- `MissionControlWidget`
- `AlertBanner`
- `FailureClusterPanel`
- `FailureHotspotPanel`
- `ReplayExplorer`
- `IncidentWorkbench`
- `RecommendationInbox`
- `ReportViewer`

### Reuse existing data concepts

Prefer extending:

- run metadata,
- recommendation metadata,
- outcome records,
- incident records,
- replay records,
- trust/effectiveness reports,
- evidence-pack sections.

---

## Work Package D4C-S1.1 — Fleet Signal Model

### Goal

Represent a fleet-level signal using existing run, health, topology, trust, and incident information.

### Implementation Direction

Create a small shared builder such as:

```text
uar/core/fleet_signals.py
```

The builder should aggregate existing records into a small, serializable structure:

```text
FleetSignal
- id
- level: info | warning | critical
- scope: fleet | node | service | skill | recipe | topology
- title
- message
- affected_run_ids
- latest_run_id
- linked_incident_ids
- linked_recommendation_ids
- trust_delta
- replay_confidence
- evidence_refs
```

### Reuse Rule

Do not create a new fleet store. Compute from existing stores and metadata first.

### Tests

- Aggregates failed runs into one fleet signal.
- Includes `latest_run_id` for replay navigation.
- Includes linked incident or recommendation IDs when available.
- Degrades gracefully when trust or incident data is missing.

---

## Work Package D4C-S1.2 — Mission Control Fleet Card

### Goal

Expose fleet signal summary inside Mission Control without creating a separate dashboard.

### Implementation Direction

Extend Mission Control snapshot or operator dashboard response with:

```text
fleet_summary:
  status
  active_signals
  critical_signals
  warning_signals
  top_signal
```

### Frontend

Add a `Fleet Health` card to `MissionControlWidget` or the dashboard health tab.

Card should show:

- fleet status,
- number of active signals,
- top signal title,
- latest affected run link.

### Reuse Rule

The card opens existing replay, alert, incident, or failure panels. It must not introduce a second fleet dashboard.

### Tests

- Mission Control renders fleet card when fleet summary is present.
- Clicking latest run opens Replay Explorer.
- Missing fleet summary does not break existing Mission Control.

---

## Work Package D4C-S1.3 — Top Fleet Alert Routing

### Goal

Route the strongest fleet signal through the existing alert banner / alert summary pathway.

### Implementation Direction

Extend alert summary logic to include top fleet signal as an alert candidate.

### Reuse Rule

Use existing `AlertBanner` click-through behavior. Add a tab or target only if it maps to an existing Mission Control tab or replay/incident path.

### Tests

- Critical fleet signal appears as top alert.
- Info-level fleet signal does not interrupt operators.
- Dismiss behavior still works.
- Alert opens the relevant existing path.

---

## Work Package D4C-S1.4 — Replay and Incident Linkage

### Goal

Allow operator to move from a fleet signal into replay and incident work without a new flow.

### Implementation Direction

- Use `latest_run_id` to open Replay Explorer.
- Link `linked_incident_ids` to Incident Workbench if present.
- If no incident exists, allow existing incident creation flow to prefill from signal context.

### Reuse Rule

Do not create `FleetIncidentWorkbench`. Use existing incident routes and components.

### Tests

- Fleet signal with latest run opens replay.
- Fleet signal with incident opens existing incident path.
- New incident can be created from signal metadata.

---

## Work Package D4C-S1.5 — Outcome Capture and Trust Movement

### Goal

When an operator records an outcome from the fleet signal path, the existing recommendation/outcome/trust/effectiveness path reflects it.

### Implementation Direction

Reuse:

- `POST /api/uar/recommendations/outcome`
- recommendation metadata,
- trust/effectiveness endpoints,
- recommendation quality calculations.

If a fleet signal has no recommendation ID, attach outcome to the related recommendation when available or require incident outcome recording to produce a recommendation-linked record later.

### Reuse Rule

Do not create a parallel fleet outcome table.

### Tests

- Recording an outcome updates existing outcome records.
- Effectiveness or trust report reflects changed counts after outcome.
- Missing recommendation ID is handled explicitly and does not create orphan trust data.

---

## Work Package D4C-S1.6 — Evidence Pack v2 Section

### Goal

Evidence Pack v2 includes the fleet signal, operator action, outcome, and resulting trust movement.

### Implementation Direction

Add a reusable evidence section builder:

```text
fleet_signal_section
```

Inputs:

- fleet signals,
- affected runs,
- incidents,
- outcomes,
- trust/effectiveness snapshots.

Output:

- markdown section for evidence pack,
- source timestamps,
- linked run IDs,
- linked incident IDs,
- outcome summary,
- trust movement summary.

### Reuse Rule

Add this as a section in the existing evidence-pack generator, not a separate report pipeline.

### Tests

- Evidence pack includes fleet signal section when fleet signals exist.
- Evidence pack omits or marks section as empty when no signals exist.
- Section includes source IDs and timestamps.

---

## First Slice Completion Criteria

The slice is complete when all of the following are true:

- Mission Control shows one fleet health signal using existing data.
- Top fleet alert routes through existing alert surfaces.
- Operator can open replay from the fleet signal.
- Operator can link or update an incident from the same path.
- Outcome capture uses existing recommendation outcome logic.
- Trust/effectiveness surfaces reflect the outcome.
- Evidence Pack v2 includes a fleet signal section.
- No duplicate dashboard, store, trust formula, or fleet-specific incident system is introduced.

---

## Anti-Sprawl Review Checklist

Before merging the first slice, verify:

- [ ] No new dashboard duplicates Mission Control.
- [ ] No new fleet store is introduced.
- [ ] No new outcome table is introduced.
- [ ] No second trust score is introduced.
- [ ] No new incident system is introduced.
- [ ] Fleet signal links to replay, incident, recommendation, outcome, or evidence.
- [ ] Tests cover missing optional data.
- [ ] Evidence pack contains traceable source IDs.

---

## Recommended Commit Order

1. Add fleet signal builder and backend tests.
2. Extend Mission Control response with fleet summary.
3. Add Fleet Health card to existing Mission Control UI.
4. Route top fleet signal through existing alert summary/banner.
5. Add replay/incident linkage tests.
6. Add outcome/trust movement regression test.
7. Add Evidence Pack v2 fleet section.
8. Update roadmap docs with results and known limits.

---

## Known Limits for First Slice

- Fleet grouping may start from run metadata only.
- Node/service identity may be absent for older runs.
- Trust movement may be visible only when recommendation IDs are available.
- Incident linkage may begin as manual or semi-automatic.
- Evidence Pack v2 can start as markdown output before richer export formats.

These are acceptable if documented and tested.
