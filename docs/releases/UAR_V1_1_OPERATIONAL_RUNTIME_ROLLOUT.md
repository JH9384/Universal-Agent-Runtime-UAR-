# UAR v1.1 Operational Runtime Rollout

## Status

Architecture Freeze: ACTIVE

Phase: Operational Runtime Campaign

Current Sprint: Ω-1 Replay Confidence

Directional Lock: Issue #83 (Runtime Health Contract)

Certification Target: Silver

Release Target: v1.1.0

Trust Formula:

```text
Execution -> Evidence -> Trust -> Operations
```

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

Implementation order is fixed (locked Issue #83):

1. #74 Replay Confidence (T1)
2. #83 Runtime Health Report (T2)
3. #62 Burn-In Framework (T3)
4. #57 Certification Engine v1 (T4)
5. #70 Certification Scoring (T4)
6. #72 Mission Control v1 (T5)
7. #55 Mission Control Consolidation (T5)
8. #56 Replay Explorer v1 (T6)
9. #59 Topology Visualization v1
10. #60 Executor Decomposition Plan

No reordering without Chief Architect approval.

---

## Release Tracks

### Track A — Replay Confidence (T1)

Issues:

- #74 Replay Confidence
- #58 Replay Confidence Helper

Deliverables:

- confidence scoring (0-100)
- confidence tier
- warning generation
- confidence reports
- replay endpoint integration

### Track B — Runtime Health (T2)

Issues:

- #83 Runtime Health Report

Deliverables:

- RuntimeHealthReport contract
- health scoring (0-100)
- health tier classification
- component status map
- operator-facing health summary

### Track C — Burn-In (T3)

Issues:

- #62 Burn-In Framework

Deliverables:

- smoke runs
- soak runs
- pressure runs
- burn-in score
- reliability evidence reports

### Track D — Certification Engine (T4)

Issues:

- #57 Certification Engine v1
- #70 Certification Scoring

Deliverables:

- replay fidelity score
- event integrity score
- runtime stability score
- certification report artifact
- experimental / silver / gold levels

### Track E — Mission Control (T5)

Issues:

- #72 Mission Control v1
- #55 Mission Control v1 Consolidation

Deliverables:

- unified operator landing page
- runtime health panel
- active run overview
- replay entry points
- metrics integration

### Track F — Replay Explorer (T6)

Issues:

- #56 Replay Explorer v1

Deliverables:

- run browser
- timeline explorer
- event inspection
- confidence overlay
- run comparison
- replay export

### Track G — Topology

Issues:

- #59 Topology Visualization v1

Deliverables:

- runtime graph
- run execution graph
- failure and slow-node highlighting

### Track H — Executor Hardening

Issues:

- #60 Executor Decomposition Plan

Deliverables:

- decomposition plan
- separated retry/cache/metrics/guardrail responsibilities
- no behavior change without tests

---

## Sprint Ω-1 Replay Confidence (T1)

Issues: #74, #58

Deliverables:

- confidence scoring (0-100)
- confidence tier
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

Success condition:

Every run produces a verifiable confidence score.

---

## Sprint Ω-2 Runtime Health (T2)

Issue: #83

Deliverables:

- RuntimeHealthReport contract
- health scoring (0-100)
- health tier classification
- component status map
- active run count
- error rate
- operator-facing health summary

Success condition:

Operator knows runtime health without reading logs.

---

## Sprint Ω-3 Burn-In (T3)

Issue: #62

Deliverables:

- smoke runs
- soak runs
- pressure runs
- burn-in score
- reliability evidence report

Success condition:

Runtime generates reliability evidence under sustained load.

---

## Sprint Ω-4 Certification Engine (T4)

Issues: #57, #70

Deliverables:

- replay fidelity score
- event integrity score
- runtime stability score
- streaming stability score
- certification report generation

Artifact:

certification.md

Success condition:

Certification report can be generated from evidence.

---

## Sprint Ω-5 Mission Control (T5)

Issues: #72, #55

Deliverables:

- runtime health panel
- active runs panel
- replay entry points
- metrics overview
- streaming overview

Success condition:

Operator understands runtime state in less than 10 seconds.

---

## Sprint Ω-6 Replay Explorer (T6)

Issue: #56

Deliverables:

- run browser
- timeline explorer
- event inspection
- failure path view
- confidence overlay
- run comparison
- export support

Success condition:

Operator can explain a failed run without reading logs.

---

## Sprint Ω-7 Topology Visualization

Issue: #59

Deliverables:

- runtime graph
- run graph
- failed-node highlighting
- slow-node highlighting
- export support

---

## Sprint Ω-8 Executor Hardening

Issue: #60

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

| Area | Sprint | Status |
| --- | --- | --- |
| Replay Confidence (T1) | Ω-1 | Active |
| Runtime Health (T2) | Ω-2 | Active |
| Burn-In (T3) | Ω-3 | Pending |
| Certification Engine (T4) | Ω-4 | Pending |
| Mission Control (T5) | Ω-5 | Pending |
| Replay Explorer (T6) | Ω-6 | Pending |
| Topology | Ω-7 | Pending |
| Executor Hardening | Ω-8 | Pending |
| Smoke Burn-In | Ω-3 | Pending |
| Soak Burn-In | Ω-3 | Pending |
| Silver Certification | Ω-4 | Pending |

- [ ] Replay Confidence Complete (#74)
- [ ] Runtime Health Complete (#83)
- [ ] Burn-In Complete (#62)
- [ ] Certification Engine Complete (#57, #70)
- [ ] Mission Control Complete (#72, #55)
- [ ] Replay Explorer Complete (#56)
- [ ] Topology Complete (#59)
- [ ] Executor Hardening Complete (#60)
- [ ] Smoke PASS
- [ ] Soak PASS
- [ ] Certification Generated
- [ ] Tag v1.1.0

---

## Release Gate

UAR v1.1 is complete when:

- Replay Confidence scores every run.
- Runtime Health reports runtime state without log reading.
- Burn-In has generated reliability evidence (Smoke + Soak at minimum).
- Certification reports can be generated from evidence.
- Mission Control provides a calm operator surface.
- Replay Explorer can reconstruct and explain runs.
- Topology view exists for runtime and run-level inspection.
- Executor decomposition has an accepted plan or first safe extraction.

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
