# UAR v1.1 Operational Runtime Rollout

## Status

Architecture Freeze: ACTIVE

Phase: Operational Runtime Campaign

Current Sprint: Ω-1 Replay Confidence

Certification Target: Silver

Release Target: v1.1.0

---

## Prime Directive

The purpose of v1.1 is not to make UAR smarter.

The purpose of v1.1 is to make UAR trustworthy.

The release question is no longer:

Can UAR execute?

The release question is:

Can UAR be trusted?

---

## Release Name

UAR v1.1 — Operational Runtime

## Release Intent

Move UAR from architecture formation into operational productization.

This release does not expand the feature surface with new skill classes.
It hardens the runtime into a trusted execution substrate.

UAR should be treated as a Universal Execution Runtime rather than primarily an Agent Runtime.

The runtime exists to execute workloads.

Examples of workloads:

- Agents
- Research Pipelines
- Scientific Compute
- Codex Modules
- SUM Modules
- Future Xarvus Adapters

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

## Layer Model

### L6 UI

- apps/web
- apps/operator-dashboard

### L5 API

- FastAPI
- SSE
- REST
- Authentication

### L4 Operations

- Mission Control
- Replay Explorer
- Runtime Health
- Certification
- Topology Visualization

### L3 Runtime Services

- Persistence
- Metrics
- Cache
- Audit

### L2 Workloads

- Skills
- Recipes
- Agents
- Compute
- Research

### L1 Runtime Core

- Executor
- Planner
- Orchestrator
- Replay
- Timeline

### L0 Contracts

- GoalSpec
- StrategySpec
- RunRecord
- RuntimeEvent

---

## System of Record

Primary Truth:

RuntimeEvent

Derived Truth:

RunRecord

Replay and certification must derive from RuntimeEvent streams.

---

## Active Issue Train

Implementation order is fixed:

1. #58 Replay Confidence Helper
2. #56 Replay Explorer v1
3. #55 Mission Control v1 Consolidation
4. #57 Certification Engine v1
5. #59 Topology Visualization v1
6. #60 Executor Decomposition Plan

No reordering without Chief Architect approval.

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

## Sprint Ω-1 Replay Confidence

Deliverables:

- confidence scoring
- timestamp validation
- terminal validation
- schema validation
- replay endpoint integration

Output example:

```json
{
  "confidence": "HIGH",
  "score": 97
}
```

---

## Sprint Ω-2 Replay Explorer

Deliverables:

- timeline view
- event inspection
- failure path view
- replay confidence display
- export support

Success condition:

Operator can explain a failed run without reading logs.

---

## Sprint Ω-3 Mission Control

Deliverables:

- runtime health panel
- active runs panel
- replay entry points
- metrics overview
- streaming overview

Success condition:

Operator understands runtime state in less than 10 seconds.

---

## Sprint Ω-4 Certification Engine

Deliverables:

- replay fidelity score
- event integrity score
- runtime stability score
- streaming stability score
- certification report generation

Artifact:

certification.md

---

## Sprint Ω-5 Topology Visualization

Deliverables:

- runtime graph
- run graph
- failed-node highlighting
- slow-node highlighting
- export support

---

## Sprint Ω-6 Executor Hardening

Extract:

- retry logic
- metrics logic
- cache logic
- guardrails

Preserve:

- execution semantics
- event contracts
- replay fidelity

---

## Burn-In Campaign

Stages:

1. Smoke
2. Soak
3. Pressure
4. Certification

Required outputs:

- burnin-report.json
- certification.md

---

## Silver Certification Gate

Requirements:

- Replay Fidelity > 95%
- Event Integrity > 99%
- Runtime Stability PASS
- Streaming Stability PASS
- Smoke PASS
- Soak PASS
- Certification Generated

Gold remains a follow-on target after pressure burn-in and topology validation.

---

## Release Checklist

| Area | Status |
| --- | --- |
| Replay Confidence | Planned |
| Replay Explorer | Planned |
| Mission Control | Planned |
| Certification | Planned |
| Topology | Planned |
| Executor Hardening | Planned |
| Smoke Burn-In | Pending |
| Soak Burn-In | Pending |
| Silver Certification | Pending |

- [ ] Replay Confidence Complete
- [ ] Replay Explorer Complete
- [ ] Mission Control Complete
- [ ] Certification Engine Complete
- [ ] Topology Complete
- [ ] Executor Hardening Complete
- [ ] Smoke PASS
- [ ] Soak PASS
- [ ] Certification Generated
- [ ] Tag v1.1.0

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

An operator must be able to answer without reading code:

- What ran?
- Why did it run?
- What happened?
- Can it be replayed?
- Can it be trusted?

---

## Non-Goals

Explicitly out of scope for v1.1:

- new agent marketplace
- new swarm behaviors
- large new skill families
- new planner architecture
- major runtime redesign
- Xarvus adapters
- Codex runtime adapter
- SUM runtime adapter
- CollapseLang runtime adapter
- framework-level abstraction churn

---

## Deferred Until v1.2

The following are intentionally deferred:

- Xarvus Adapters
- Codex Runtime Adapter
- SUM Runtime Adapter
- CollapseLang Runtime Adapter
- Swarm Expansion
- Marketplace Concepts
- New Planner Architectures
- Major Runtime Redesigns

---

## Current Maturity Assessment

| Area | Completion |
| --- | --- |
| Contracts | 95% |
| Runtime Core | 90% |
| Skills | 90% |
| Persistence | 90% |
| API | 85% |
| UI | 75% |
| Replay | 70% |
| Mission Control | 65% |
| Certification | 50% |
| Topology | 40% |

Overall Architecture Completion: ~90%

Overall Platform Completion: ~80–85%

The remaining work is operational trust infrastructure.

---

## Chief Architect Rule

Every pull request must answer:

"Does this make UAR a more trustworthy execution runtime?"

If the answer is no, defer the work until after v1.1 certification.
