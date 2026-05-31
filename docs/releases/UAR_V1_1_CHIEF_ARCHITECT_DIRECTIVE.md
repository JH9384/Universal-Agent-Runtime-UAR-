# UAR v1.1 Chief Architect Directive

## Status

Architecture Freeze v1.1 is now active.

UAR is to be treated as a Universal Execution Runtime.

Agent behavior, scientific compute, research workflows, Codex, SUM, CollapseLang, and future Xarvus modules are workload classes that consume the runtime.

---

## Prime Directive

The release question is no longer:

Can UAR execute?

The release question is:

Can UAR be trusted?

---

## Allowed Work

Only the following categories are authorized during v1.1:

- Replay Explorer
- Replay confidence
- Mission Control
- Runtime Health
- Certification Engine
- Topology Visualization
- Executor hardening
- Burn-in automation

---

## Frozen Work

The following are deferred until after v1.1 certification:

- new planner architecture
- new agent marketplace concepts
- swarm expansion
- large new skill families
- major runtime redesign
- framework-level abstraction churn

---

## Locked Contracts

The following are locked unless a defect proves the contract unsafe:

- GoalSpec
- StrategySpec
- RunRecord
- RuntimeEvent
- Workload Contract v1
- Runtime Boundary Audit
- Replay-first operational model

---

## Issue Train

Implementation proceeds in this order:

1. #58 Replay Confidence Helper
2. #56 Replay Explorer v1
3. #55 Mission Control v1 Consolidation
4. #57 Certification Engine v1
5. #59 Topology Visualization v1
6. #60 Executor Decomposition Plan

---

## Release Gate

UAR v1.1 is complete when an operator can answer without reading code:

- What ran?
- Why did it run?
- What happened?
- Can it be replayed?
- Can it be trusted?

---

## Certification Target

Target: Silver

Silver requires:

- replay confidence integrated
- Mission Control usable
- certification report generation
- smoke burn-in passed
- soak burn-in passed
- event integrity validated

Gold remains a follow-on target after pressure burn-in and topology validation.

---

## Operating Rule

Every PR must answer:

Does this make UAR a more trustworthy execution runtime?

If the answer is no, defer it.
