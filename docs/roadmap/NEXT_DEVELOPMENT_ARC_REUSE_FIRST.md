# UAR Next Development Arc — Reuse-First Operational Control Plane

> Status: Proposed baseline  
> Date: 2026-06-07  
> Posture: Open development, reuse-first, anti-sprawl

---

## Executive Summary

The next UAR development arc turns the system from a capable agent runtime into a reusable operational control plane for trustworthy agent operations.

The focus is not feature accumulation. The focus is composition: reuse existing UAR primitives, connect them into a single operator loop, and avoid duplicating panels, APIs, storage paths, or trust logic.

The development theme is:

**Observe fleet → investigate failures → replay evidence → act → record outcome → update trust → generate report.**

This arc should complete the transition from runtime plus dashboards into an operational intelligence layer with disciplined reuse.

---

## Guiding Principle

**Build freely. Reuse aggressively. Avoid sprawl. Keep the evidence trail clean.**

Every new capability should answer four questions before implementation:

1. Can an existing router, panel, store method, report, or trust primitive be reused?
2. Does this strengthen the operator loop, or does it create another isolated surface?
3. Does it preserve replay, evidence, outcome, and audit continuity?
4. Can it be tested without creating new architectural weight?

If the answer to any of these is unclear, the work should be reshaped before implementation.

---

## Non-Goals

This arc should not create a second platform beside UAR.

Avoid:

- Duplicate dashboards that show the same operational truth.
- Parallel API families for the same data.
- New storage paths when existing run, metadata, outcome, evidence, or report stores can be extended.
- Trust formulas that bypass the existing trust/evidence spine.
- One-off panels with no operator workflow role.
- Fleet features that cannot link back to replay, incidents, recommendations, outcomes, or evidence packs.

---

## Core Product Loop

The next arc centers on one reusable loop:

```text
Fleet State
  → Signal / Alert
  → Operator Triage
  → Replay / Evidence
  → Incident or Recommendation Action
  → Outcome Capture
  → Trust Update
  → Evidence Pack / Report
  → Next Briefing
```

This loop should be visible across the UI, API, tests, and docs.

---

## Phase 1 — D4C Fleet Operations, Reusing Existing Mission Control

### Goal

Make UAR show the operational state of multiple runs, nodes, agents, or services without creating a separate fleet product.

### Reuse Targets

- Reuse Mission Control as the primary fleet entry point.
- Reuse Runtime Health scoring where possible.
- Reuse Replay Explorer for failed or suspicious runs.
- Reuse FailureClusterPanel and FailureHotspotPanel for fleet-level patterns.
- Reuse existing alert summary and trust drift surfaces.
- Reuse existing store and metadata paths for fleet attributes.

### Deliverables

- Fleet Health summary inside Mission Control.
- Node or service grouping for runs.
- Trust drift by fleet segment.
- Replay confidence by fleet segment.
- Failure recurrence by node, service, skill, recipe, or topology segment.
- Fleet-level top alert that opens the relevant existing panel instead of a new screen.

### Acceptance Criteria

- Fleet status links directly to replay, incidents, recommendations, or evidence.
- No duplicate health scoring engine is created.
- No separate fleet dashboard exists unless it is a composed view of existing panels.
- Tests cover aggregation, filtering, and failure-path navigation.

---

## Phase 2 — Evidence Pack v2 as a Reusable Product Artifact

### Goal

Turn evidence packs into the canonical output of UAR operational truth.

### Reuse Targets

- Reuse trust validation reports.
- Reuse burn-in comparison reports.
- Reuse alert accuracy reports.
- Reuse replay confidence evidence.
- Reuse incident and outcome data.
- Reuse certification package generation.

### Deliverables

Evidence Pack v2 should support:

- Daily operational evidence pack.
- Deployment-readiness pack.
- Incident postmortem pack.
- Certification pack.
- Fleet health pack.

Each pack should share one report-generation spine rather than separate generators for each artifact.

### Acceptance Criteria

- A single evidence-pack orchestrator composes reusable sections.
- Every section states its source data and timestamp.
- Reports can be regenerated deterministically from stored records.
- Evidence packs link to relevant runs, incidents, recommendations, outcomes, and replay paths.

---

## Phase 3 — Operator Daily Loop

### Goal

Make UAR useful as a daily operational console, not just a diagnostic tool.

### Reuse Targets

- Reuse Morning Briefing.
- Reuse Recommendation Inbox.
- Reuse Incident Workbench.
- Reuse Trust Explorer.
- Reuse Replay Explorer.
- Reuse Report Viewer.
- Reuse existing alerts and activity log.

### Daily Flow

1. Open Morning Briefing.
2. Review Fleet Health.
3. Open top alert.
4. Inspect trust drift or failure cluster.
5. Launch replay for the relevant run.
6. Record action or outcome.
7. File or update incident.
8. Generate evidence pack.
9. Feed the next briefing.

### Acceptance Criteria

- The operator can complete the loop without leaving UAR.
- Each step reuses an existing UAR surface or endpoint where possible.
- Outcome capture updates later trust/effectiveness analysis.
- The next briefing reflects prior recorded outcomes and incidents.

---

## Phase 4 — Incident Intelligence Loop

### Goal

Connect incidents, recommendations, outcomes, replay, and trust into one closed learning loop.

### Reuse Targets

- Reuse incident records.
- Reuse recommendation IDs and metadata.
- Reuse recommendation outcomes.
- Reuse replay linkage.
- Reuse trust/effectiveness/calibration/evidence endpoints.

### Canonical Chain

```text
Run → Failure → Recommendation → Operator Action → Outcome → Recurrence → Trust Update
```

### Deliverables

- Incident recurrence detection.
- Recommendation success/failure summary per incident type.
- Trust movement after outcomes.
- Replay-backed incident summaries.
- Incident-to-evidence-pack export.

### Acceptance Criteria

- No incident intelligence exists without links to stored operational records.
- Recommendations can be evaluated by actual outcomes.
- Recurring incidents affect briefing and evidence reports.
- Tests cover the full chain from run to outcome to trust signal.

---

## Phase 5 — Trust Formula Workbench

### Goal

Allow trust, ranking, evidence, and drift formulas to evolve safely through replay-backed comparison.

### Reuse Targets

- Reuse existing trust computation inputs.
- Reuse historical outcomes.
- Reuse replay evidence.
- Reuse report viewer and evidence pack output.
- Reuse test fixtures from trust ranking and recommendation tests.

### Deliverables

- Compare current formula against candidate formulas.
- Show false-priority reduction, missed-alert risk, ranking stability, and calibration movement.
- Produce a formula comparison report.
- Keep production formula unchanged unless explicitly promoted.

### Acceptance Criteria

- Formula experiments are isolated from production ranking.
- Each candidate is evaluated against historical outcomes and replay evidence.
- Formula promotion requires tests and documentation updates.
- No formula bypasses the trust/evidence spine.

---

## Phase 6 — Certification States

### Goal

Translate UAR evidence into simple readiness states.

### Reuse Targets

- Reuse runtime health.
- Reuse replay confidence.
- Reuse burn-in results.
- Reuse alert accuracy.
- Reuse trust calibration.
- Reuse outcome correlation.
- Reuse incident recurrence.
- Reuse security posture checks.

### Candidate States

- Development Ready
- Staging Ready
- Burn-In Certified
- Release Candidate
- Production Stable
- Degraded
- Untrusted

### Acceptance Criteria

- Certification state is explainable from evidence, not manually assigned.
- Each state links to evidence-pack sections.
- Operators can see why a state changed.
- State transitions are covered by tests.

---

## Phase 7 — Security and Deployment Hardening

### Goal

Make UAR safer to run in serious environments without creating a separate security subsystem.

### Reuse Targets

- Reuse audit logs.
- Reuse evidence packs.
- Reuse deployment manifests.
- Reuse SBOM and security tests.
- Reuse existing auth tiers.
- Reuse encryption-at-rest wrapper.

### Deliverables

- Production-mode encryption-key validation.
- Secret hygiene checks.
- Signed or checksummed evidence packs.
- Immutable audit trail verification.
- Deployment posture report.
- Persistent storage recommendation for production deployments.

### Acceptance Criteria

- Invalid production encryption configuration fails fast.
- Evidence artifacts are tamper-evident.
- Deployment checks are surfaced in the same evidence-pack system.
- Security checks reuse existing reports and tests where possible.

---

## Phase 8 — UOR Alignment Layer

### Goal

Strengthen UAR as the runtime evidence layer for UOR-aligned systems.

### Reuse Targets

- Reuse UOR witness fields.
- Reuse artifact validation.
- Reuse replay records.
- Reuse provenance and evidence pack outputs.
- Reuse addressable run records.

### Deliverables

- UOR witness visibility in replay and evidence packs.
- UOR alignment drift checks.
- Addressable execution records for certified runs.
- UOR artifact validation in deployment and report flows.

### Acceptance Criteria

- UOR alignment adds meaning to existing records instead of creating a parallel record system.
- Evidence packs can include UOR witness and validation status.
- UOR drift is surfaced as an operational signal.

---

## Phase 9 — Plugin Registry, Later and Carefully

### Goal

Prepare for trusted plugins only after evidence, fleet, security, and certification loops are mature.

### Reuse Targets

- Reuse skill registry.
- Reuse trust/evidence scoring.
- Reuse replay confidence.
- Reuse incident history.
- Reuse operator approval flows.

### Deliverables

- Plugin capability metadata.
- Plugin trust profile.
- Plugin failure history.
- Plugin replay confidence.
- Plugin certification status.

### Acceptance Criteria

- No plugin is trusted without operational evidence.
- Plugin installation does not bypass audit, replay, or outcome capture.
- Plugin registry reuses skill and trust infrastructure.

---

## Phase 10 — Boring Mode

### Goal

Create a no-drama operator view that shows only what matters.

### Reuse Targets

- Reuse Mission Control.
- Reuse top alerts.
- Reuse trust drift.
- Reuse evidence pack status.
- Reuse incidents and recommendation inbox.

### Surface

Boring Mode answers:

- What is broken?
- What changed?
- What evidence supports it?
- What action is recommended?
- What happened last time?
- Is confidence improving or degrading?

### Acceptance Criteria

- No decorative complexity.
- No duplicate logic.
- Every displayed item links to evidence.
- Operators can use it as the default daily view.

---

## Reuse-First Design Rules

### 1. Compose before creating

Before building a new component, check whether Mission Control, Dashboard, Report Viewer, Trust Explorer, Replay Explorer, Incident Workbench, Recommendation Inbox, or existing panels can be composed.

### 2. Extend existing stores before adding storage

Prefer extending run metadata, recommendation metadata, outcome records, incident records, audit records, and evidence-pack outputs.

### 3. One truth per concept

There should be one canonical source for:

- runtime health,
- replay confidence,
- trust score,
- recommendation quality,
- outcome attribution,
- incident recurrence,
- evidence-pack sections,
- fleet health.

### 4. All roads lead to replay or evidence

Any alert, insight, incident, recommendation, or certification state should link back to replay evidence, stored records, or generated reports.

### 5. Product loops beat feature lists

A new feature is only valuable if it strengthens the operator loop.

---

## First Implementation Slice

Start small and complete one end-to-end path:

**Fleet Health card → top fleet alert → replay → incident update → outcome capture → trust movement → evidence-pack section.**

This slice proves the whole arc without building every phase first.

### Slice Acceptance Criteria

- One fleet signal appears in Mission Control.
- The signal opens the relevant replay or incident path.
- Operator can record an outcome.
- Trust/effectiveness surfaces reflect the outcome.
- Evidence Pack v2 includes the fleet signal, action, outcome, and resulting trust movement.
- No duplicate dashboard, store, or scoring path is introduced.

---

## Success Definition

This arc is complete when UAR can support a repeatable operational day:

1. Operator opens briefing.
2. UAR identifies fleet-level risk.
3. Operator investigates through replay and evidence.
4. Operator records action and outcome.
5. UAR updates trust and incident intelligence.
6. UAR generates an evidence pack.
7. Next briefing incorporates what happened.

If that loop works cleanly, UAR has become a reusable operational control plane rather than a collection of impressive parts.
