# UAR v1.1 Operational Runtime Rollout

## Release Name

UAR v1.1 — Operational Runtime

## Release Intent

Move UAR from architecture formation into operational productization.

This release does not expand the feature surface with new skill classes.
It hardens the runtime into a trusted execution substrate.

---

## Architecture Freeze

The following are locked for v1.1:

- GoalSpec
- StrategySpec
- RunRecord
- RuntimeEvent
- Workload Contract v1
- Runtime Boundary Audit
- Replay-first operational model
- Mission Control as observer layer

No major redesign should occur during this release train.

---

## Release Tracks

### Track A — Replay Explorer

Issues:

- #56 Replay Explorer v1
- #58 Replay Confidence Helper

Deliverables:

- replay confidence scoring
- failure path projection
- event inspection
- replay export

### Track B — Mission Control

Issues:

- #55 Mission Control v1 Consolidation

Deliverables:

- unified operator landing page
- runtime health summary
- active run overview
- replay entry points
- metrics integration

### Track C — Certification

Issues:

- #57 Certification Engine v1

Deliverables:

- replay fidelity score
- event integrity score
- runtime stability score
- certification report artifact

### Track D — Topology

Issues:

- #59 Topology Visualization v1

Deliverables:

- runtime graph
- run execution graph
- failure and slow-node highlighting

### Track E — Executor Hardening

Issues:

- #60 Executor Decomposition Plan

Deliverables:

- decomposition plan
- separated retry/cache/metrics/guardrail responsibilities
- no behavior change without tests

---

## Rollout Order

1. Replay Confidence Helper
2. Replay Explorer v1
3. Mission Control v1 Consolidation
4. Certification Engine v1
5. Topology Visualization v1
6. Executor Decomposition
7. Burn-in and Certification Run

---

## Release Gate

UAR v1.1 is complete when:

- Replay Explorer can reconstruct and explain runs.
- Mission Control provides a calm operator surface.
- Certification reports can be generated.
- Runtime health is visible.
- Topology view exists for runtime and run-level inspection.
- Executor decomposition has an accepted plan or first safe extraction.
- Burn-in passes at least Smoke and Soak levels.

---

## Non-Goals

Explicitly out of scope for v1.1:

- new agent marketplace
- new swarm behaviors
- large new skill families
- new planner architecture
- major runtime redesign

---

## Chief Architect Rule

Every change must answer:

Does this make UAR a more trustworthy execution runtime?

If not, defer it until after v1.1.
