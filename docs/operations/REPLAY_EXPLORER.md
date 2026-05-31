# UAR Replay Explorer

Replay Explorer is the operator-facing reconstruction layer for UAR runs.

Its purpose is to answer three questions:

1. What happened?
2. Why did it happen?
3. Can the run be reconstructed from recorded RuntimeEvents?

---

## Source of Truth

Replay Explorer must treat the RuntimeEvent stream as the primary source of truth.

A valid replayable run requires:

- a `start` event
- one or more execution events
- a terminal `complete` event
- one `run_id`
- one `goal_id`
- valid `uar.event.v1` event schema

---

## Replay Views

### Run Summary

Shows:

- run ID
- goal ID
- status
- skill count
- event count
- error count
- output summary

### Timeline View

Projects the event stream into chronological phases:

```text
Run
  -> Recipe
      -> Skill
          -> Event
```

### Failure Path View

Shows:

- first failure
- retry sequence
- failed skill or recipe
- downstream skipped or suppressed work
- final terminal state

### Recipe Expansion View

Shows:

- requested execution order
- expanded skill order
- recipe boundaries
- skipped recipes
- nested recipe starts and ends

### Event Detail View

Shows raw event details:

- type
- timestamp
- skill
- payload
- error
- correlation ID
- UOR address and witness, when present

---

## Replay Confidence

Replay confidence should be computed from:

- schema validity
- terminal event presence
- monotonic timestamp sanity
- run ID consistency
- goal ID consistency
- missing event detection
- complete/failure status agreement

Suggested levels:

```text
HIGH    = valid schema, complete event stream, no contradictions
MEDIUM  = valid schema with warning-level gaps
LOW     = partial stream or inconsistent terminal state
FAILED  = unreplayable event stream
```

---

## MVP Requirements

Replay Explorer v1 is complete when operators can:

1. Select a run.
2. View the timeline.
3. Inspect every event.
4. Identify failed skills or recipes.
5. See replay confidence.
6. Export the replay summary.

---

## Non-Goals

Replay Explorer is not an autonomous repair engine yet.

It should not mutate run records, retry production workloads, or silently rewrite event history.
