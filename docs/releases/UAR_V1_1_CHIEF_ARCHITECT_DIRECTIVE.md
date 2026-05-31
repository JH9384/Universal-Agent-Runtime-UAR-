# UAR v1.1 Chief Architect Directive

## Status

Architecture Freeze v1.1 is ACTIVE.

UAR is to be treated as a Universal Execution Runtime.

---

## Canonical Plan

The authoritative implementation, rollout, certification, burn-in, and release plan for v1.1 is maintained in:

`docs/releases/UAR_V1_1_OPERATIONAL_RUNTIME_ROLLOUT.md`

This document is the single source of truth for:

- implementation sequencing
- active issue train
- sprint planning
- certification gates
- burn-in requirements
- release criteria

---

## Prime Directive

The purpose of v1.1 is not to make UAR smarter.

The purpose of v1.1 is to make UAR trustworthy.

---

## Architecture Freeze

Locked contracts:

- GoalSpec
- StrategySpec
- RunRecord
- RuntimeEvent
- Workload Contract v1
- Runtime Boundary Audit

No major redesigns are authorized during v1.1.

---

## Operating Rule

Every pull request must answer:

"Does this make UAR a more trustworthy execution runtime?"

If the answer is no, defer it until after v1.1 certification.
