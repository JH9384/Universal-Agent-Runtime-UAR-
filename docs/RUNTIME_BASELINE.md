# UAR Runtime Baseline

## Purpose

This document locks the base runtime substrate that UAR needs before any other-side modules attach.

This is the baseline for burn-in, validation, merge review, and future module integration.

---

## Baseline Identity

UAR immediate-side runtime is:

```text
a deterministic, event-oriented, replayable execution substrate
```

It is not yet:

```text
a cognition platform
a semantic evaluator
a DSE engine
a symbolic orchestration layer
a multi-agent swarm environment
```

Those attach later as consumers.

---

## Baseline Runtime Chain

The locked runtime chain is:

```text
GoalSpec
-> PlannerRouter
-> RuntimeConfig
-> StrategySpec
-> Executor
-> RuntimeEvents
-> Replay Validation
-> RunRecord Reconstruction
-> Timeline Projection
-> Certification
```

Everything in this chain must remain boring, repeatable, and testable.

---

## Execution Truth

Execution truth is:

```text
RuntimeEvent trace
```

Derived structures:

```text
RunRecord
Replay summary
Timeline projection
Certification result
UI timeline
Observer input
```

Derived structures must not redefine execution truth.

---

## Frozen Immediate-Side Components

These are the current baseline components:

```text
uar/core/config.py
uar/core/planner.py
uar/core/events.py
uar/core/executor_events.py
uar/core/replay.py
uar/core/timeline.py
uar/core/certification.py
```

Supporting validation:

```text
tests/test_planner_router.py
tests/test_runtime_config.py
tests/test_runtime_events.py
tests/test_replay_integrity.py
tests/test_timeline.py
tests/test_runtime_trace_fixtures.py
tests/test_replay_certification.py
```

Golden fixtures:

```text
tests/fixtures/runtime_trace_success.json
tests/fixtures/runtime_trace_failure.json
```

Operational burn-in:

```text
scripts/burn_in.sh
.github/workflows/runtime-burn-in.yml
```

Governance docs:

```text
SYSTEM.md
CONFORMANCE.md
docs/BURN_IN_PLAN.md
docs/BURN_IN_CHECKLIST.md
docs/GOLDEN_TRACE_POLICY.md
docs/RUNTIME_MATH_AND_VISUALS.md
docs/RUNTIME_BASELINE.md
```

---

## Baseline Guarantees

The baseline guarantees:

```text
[ ] PlannerRouter is deterministic by default
[ ] Adaptive planning requires explicit opt-in
[ ] RuntimeConfig validates deployment-sensitive settings
[ ] RuntimeEvents use schema uar.event.v1
[ ] Replay validates event lifecycle
[ ] RunRecord is reconstructed from RuntimeEvents
[ ] Timeline projection is derived from RuntimeEvents
[ ] Golden traces encode success and failure lifecycles
[ ] Trace normalization separates volatile fields from semantics
[ ] Payload drift remains semantic
[ ] Burn-in has one canonical runner
```

---

## Baseline Non-Goals

The baseline does not include:

```text
observers
DSE overlays
semantic scoring
symbolic execution overlays
memory graph cognition
multi-agent orchestration
advanced timeline graphing
production database replacement
new skill systems
new planner intelligence
```

Those are later modules.

---

## Future Module Attachment Rule

Future modules may consume:

```text
RuntimeEvents
RunRecords
Replay summaries
Timeline projections
Certification results
```

Future modules may not:

```text
change event truth silently
mutate replay semantics
redefine RunRecord meaning
hide payload drift through normalization
couple cognition directly into executor behavior
```

---

## Baseline Burn-In Command

Canonical local command:

```bash
./scripts/burn_in.sh
```

Expected result:

```text
all targeted runtime tests pass
make gate passes
no feature expansion occurs
```

---

## Baseline Merge Readiness

The baseline is merge-ready when:

```text
[ ] burn_in.sh passes locally
[ ] runtime-burn-in workflow passes
[ ] executor event helper delegates to make_executor_event
[ ] golden trace tests pass
[ ] certification tests pass
[ ] docs agree on immediate-side boundary
[ ] no other-side module scope appears in the diff
```

---

## Base Principle

```text
Make the substrate stable enough that future intelligence can trust it.
```
