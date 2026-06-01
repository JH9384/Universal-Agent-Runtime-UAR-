# UAR v1.1 Execution Campaign

## Purpose

Translate the Architecture Freeze and Operational Runtime rollout into a concrete execution campaign.

This document is the implementation companion to:

- UAR_V1_1_CHIEF_ARCHITECT_DIRECTIVE.md
- UAR_V1_1_OPERATIONAL_RUNTIME_ROLLOUT.md

---

## Architecture Freeze

The following remain locked:

- GoalSpec
- StrategySpec
- RunRecord
- RuntimeEvent
- Workload Contract v1
- Runtime Boundary Audit

Major redesign is out of scope.

---

## Directional Lock

Issue #83 (Runtime Health Contract) locked the priority order.

Trust formula:

```text
Execution -> Evidence -> Trust -> Operations
```

## Active Issue Train

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

---

## Sprint Ω-1 Replay Confidence (T1)

Issues: #74, #58

Deliver:

- confidence scoring (0-100)
- confidence tier
- terminal validation
- timestamp validation
- schema validation
- replay endpoint integration

---

## Sprint Ω-2 Runtime Health (T2)

Issue: #83

Deliver:

- RuntimeHealthReport contract
- health scoring (0-100)
- health tier classification
- component status map
- operator-facing health summary

---

## Sprint Ω-3 Burn-In (T3)

Issue: #62

Deliver:

- smoke runs
- soak runs
- pressure runs
- reliability evidence report

---

## Sprint Ω-4 Certification Engine (T4)

Issues: #57, #70

Deliver:

- replay fidelity score
- event integrity score
- runtime stability score
- certification report generation

---

## Sprint Ω-5 Mission Control (T5)

Issues: #72, #55

Deliver:

- runtime health panel
- active runs panel
- replay entry points
- metrics overview
- streaming overview

---

## Sprint Ω-6 Replay Explorer (T6)

Issue: #56

Deliver:

- run browser
- timeline explorer
- event inspection
- failure path view
- confidence overlay
- run comparison
- export support

---

## Sprint Ω-7 Topology Visualization

Issue: #59

Deliver:

- runtime graph
- run graph
- failed-node highlighting
- slow-node highlighting
- export support

---

## Sprint Ω-8 Executor Hardening

Issue: #60

Extract:

- retry policies
- metrics emission
- cache/coalescing logic
- guardrails

Preserve runtime semantics.

---

## Burn-In Sequence

1. Smoke Burn-In
2. Soak Burn-In
3. Pressure Burn-In
4. Certification Run

---

## Silver Certification Gate

Required:

- Replay Fidelity > 95%
- Event Integrity > 99%
- Runtime Stability PASS
- Streaming Stability PASS
- Certification Report Generated

---

## Release Checklist

[ ] Replay Confidence complete (#74)
[ ] Runtime Health complete (#83)
[ ] Burn-In complete (#62)
[ ] Certification Engine complete (#57, #70)
[ ] Mission Control complete (#72, #55)
[ ] Replay Explorer complete (#56)
[ ] Topology complete (#59)
[ ] Executor decomposition complete (#60)
[ ] Smoke burn-in passed
[ ] Soak burn-in passed
[ ] Certification report generated
[ ] v1.1 tag created

---

## Deferred to v1.2

- Xarvus adapters
- Codex integration
- SUM integration
- CollapseLang integration
- Advanced workload orchestration

---

## Chief Architect Rule

Every PR must answer:

"Does this make UAR a more trustworthy execution runtime?"

If not, defer it until after v1.1 certification.
