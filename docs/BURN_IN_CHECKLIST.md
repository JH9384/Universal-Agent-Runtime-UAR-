# UAR Burn-In Operational Checklist

## Purpose

This checklist keeps burn-in boring, repeatable, and non-expansive.

Use it before every burn-in run and before accepting changes during the burn-in phase.

---

## 1. Scope Check

Before running or changing anything, confirm:

```text
[ ] No new feature scope is being added
[ ] No observer/DSE/semantic/cognition module is being introduced
[ ] No new planner behavior is being added
[ ] No new skill behavior is being added
[ ] No runtime semantics are changing without explicit documentation
```

If any box fails, stop.

---

## 2. Run the Canonical Burn-In Path

```bash
./scripts/burn_in.sh
```

This is the preferred path.

Avoid ad hoc test mixes unless debugging a specific failure.

---

## 3. Targeted Debug Path

If burn-in fails, use the narrowest relevant test:

```bash
pytest tests/test_planner_router.py -q
pytest tests/test_runtime_config.py -q
pytest tests/test_runtime_events.py -q
pytest tests/test_replay_integrity.py -q
pytest tests/test_timeline.py -q
pytest tests/test_runtime_trace_fixtures.py -q
pytest tests/test_replay_certification.py -q
```

Fix only the failing contract.

Do not work around a failure by adding a feature.

---

## 4. Golden Trace Protection

Before changing any fixture under:

```text
tests/fixtures/
```

confirm:

```text
[ ] The fixture change reflects an intentional runtime contract change
[ ] The event order remains valid
[ ] Payload drift is intentional and documented
[ ] Replay and certification tests are updated
[ ] docs/GOLDEN_TRACE_POLICY.md still applies
```

If not, do not change the fixture.

---

## 5. Executor Adapter Swap Check

When wiring executor events to `make_executor_event(...)`, confirm:

```text
[ ] event type is unchanged
[ ] run_id is unchanged
[ ] goal_id is unchanged
[ ] skill is unchanged
[ ] payload is unchanged
[ ] error is unchanged
[ ] correlation_id remains optional metadata
[ ] event order is unchanged
```

Then run:

```bash
./scripts/burn_in.sh
```

---

## 6. Stop Conditions

Stop burn-in work and investigate if:

```text
[ ] trace ordering changes unexpectedly
[ ] payload shape changes unexpectedly
[ ] replay reconstruction changes unexpectedly
[ ] timeline summaries change unexpectedly
[ ] normalization hides meaningful payload drift
[ ] make gate fails
[ ] docs disagree about runtime truth
```

---

## 7. Pass Conditions

A burn-in pass is clean when:

```text
[ ] ./scripts/burn_in.sh passes
[ ] targeted tests pass when run individually
[ ] fixtures remain unchanged unless intentionally updated
[ ] no new feature scope appears in the diff
[ ] docs remain consistent
```

---

## 8. Guiding Sentence

```text
Boring is the point.
```

The goal is repeatable proof, not novelty.
