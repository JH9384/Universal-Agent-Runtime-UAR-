# UAR Runtime Burn-In Plan

## Purpose

This document freezes feature expansion and defines the burn-in process for the immediate-side UAR runtime substrate.

The goal is not to add more capability.

The goal is to prove that the current substrate is stable, deterministic, replayable, inspectable, and safe to build on later.

---

## Burn-In Boundary

### In Scope

```text
RuntimeConfig
PlannerRouter
StrategySpec
RuntimeEvent builders
Executor event adapter
Replay validation
RunRecord reconstruction
Timeline projection
Trace fixtures
Trace normalization
Trace equivalence
Runtime math and visual docs
Conformance docs
make gate
```

### Out of Scope

```text
new planners
new skills
new observers
DSE overlays
semantic evaluators
memory graph cognition
symbolic overlays
multi-agent orchestration
advanced UI visualizations
new persistence backends
```

If a change is not required to make the existing runtime substrate stable, tested, or documented, it waits.

---

## Burn-In Principle

```text
No more features until execution truth is proven.
```

Execution truth is defined by:

```text
RuntimeEvent trace -> Replay -> RunRecord -> Timeline Projection
```

---

## Required Burn-In Checks

### 1. Version and Release Gate

```bash
make version
make sync-version
git diff -- pyproject.toml VERSION
make gate
```

Expected:

- `VERSION` and `pyproject.toml` agree
- `make gate` passes
- no unexpected version drift remains

---

### 2. Targeted Runtime Tests

```bash
pytest tests/test_planner_router.py -q
pytest tests/test_runtime_config.py -q
pytest tests/test_runtime_events.py -q
pytest tests/test_replay_integrity.py -q
pytest tests/test_timeline.py -q
pytest tests/test_runtime_trace_fixtures.py -q
pytest tests/test_replay_certification.py -q
```

Expected:

- planner routing is deterministic and fail-closed
- runtime config rejects invalid deployment values
- RuntimeEvents are schema-valid
- replay validates event streams
- timeline projection is stable
- trace fixtures replay cleanly
- trace normalization behaves as expected

---

### 3. Fixture Replay Path

For each canonical fixture:

```text
tests/fixtures/runtime_trace_success.json
tests/fixtures/runtime_trace_failure.json
```

Prove:

```text
fixture -> validate_event_stream -> run_record_from_events -> project_timeline -> summarize_timeline
```

Expected:

- success fixture reconstructs a completed RunRecord
- failure fixture reconstructs a failed RunRecord
- both produce deterministic timeline summaries

---

### 4. Certification Path

Prove:

```text
normalize_trace(T) == normalize_trace(T')
```

when traces differ only by:

```text
timestamp
correlation_id
optional generated run_id / goal_id when ID normalization is enabled
```

Prove inequality when traces differ by:

```text
event type
payload
ordering
error semantics
```

---

### 5. Documentation Consistency

Review:

```text
SYSTEM.md
CONFORMANCE.md
docs/RUNTIME_MATH_AND_VISUALS.md
docs/BURN_IN_PLAN.md
```

Expected:

- all docs agree on deterministic-first runtime posture
- other-side modules remain out of scope
- RuntimeEvents remain execution truth
- replay and timeline are projections, not independent semantics

---

## Executor Adapter Burn-In

The final executor event migration should be minimal.

Target local diff:

```python
from uar.core.executor_events import make_executor_event
```

Then change the central executor `_event(...)` helper to delegate to:

```python
make_executor_event(
    event_type,
    run_id,
    goal_id,
    skill=skill,
    payload=payload,
    error=error,
    correlation_id=correlation_id,
)
```

Do not change event order.
Do not change event payloads.
Do not change execution behavior.
Do not expand executor features.

---

## Burn-In Success Criteria

The burn-in phase is complete when:

```text
[ ] make gate passes
[ ] targeted runtime tests pass
[ ] success/failure fixtures replay correctly
[ ] trace certification tests pass
[ ] docs agree on boundaries
[ ] executor event helper delegates to canonical adapter
[ ] no other-side modules are introduced
[ ] no new feature scope is added
```

---

## Burn-In Failure Rules

If a test fails:

1. fix the smallest contract violation
2. add or adjust the narrowest test
3. do not add a new feature to work around it
4. do not weaken replay/event semantics without documenting why

If the executor migration changes behavior:

1. revert the executor helper change
2. keep the adapter module
3. compare before/after event traces
4. retry with a smaller patch

---

## Final Burn-In Output

At the end of burn-in, UAR should be confidently described as:

```text
a deterministic, event-oriented, replayable runtime substrate
```

Not yet:

```text
a cognition platform
an observer system
a semantic evaluator
a DSE runtime
an autonomous multi-agent environment
```

Those attach later through stable runtime outputs.

---

## Guiding Sentence

```text
Freeze expansion. Prove the substrate.
```
