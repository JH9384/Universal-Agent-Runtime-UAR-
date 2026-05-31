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

## Active Issue Train

1. #58 Replay Confidence Helper
2. #56 Replay Explorer v1
3. #55 Mission Control v1 Consolidation
4. #57 Certification Engine v1
5. #59 Topology Visualization v1
6. #60 Executor Decomposition Plan

---

## Sprint Ω-1 Replay Confidence

Deliver:

- confidence scoring
- terminal validation
- timestamp validation
- schema validation
- replay endpoint integration

---

## Sprint Ω-2 Replay Explorer

Deliver:

- timeline view
- event inspection
- failure path view
- replay confidence display
- export support

---

## Sprint Ω-3 Mission Control

Deliver:

- runtime health panel
- active runs panel
- replay entry points
- metrics overview
- streaming overview

---

## Sprint Ω-4 Certification Engine

Deliver:

- replay fidelity score
- event integrity score
- runtime stability score
- certification report generation

---

## Sprint Ω-5 Topology Visualization

Deliver:

- runtime graph
- run graph
- failed-node highlighting
- slow-node highlighting
- export support

---

## Sprint Ω-6 Executor Hardening

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

[ ] Replay confidence implemented
[ ] Replay Explorer implemented
[ ] Mission Control consolidated
[ ] Certification engine implemented
[ ] Topology visualization implemented
[ ] Executor decomposition completed
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
