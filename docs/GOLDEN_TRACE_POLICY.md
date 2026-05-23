# UAR Golden Trace Policy

## Purpose

Golden traces are canonical runtime event traces used to prove that replay,
timeline projection, and certification behavior remain stable during burn-in.

They are not examples to casually edit.
They are behavioral contracts.

---

## Current Golden Traces

```text
tests/fixtures/runtime_trace_success.json
tests/fixtures/runtime_trace_failure.json
```

These traces define the minimum stable lifecycle shapes for:

```text
successful execution
failed execution
```

---

## Golden Trace Rules

### 1. Do Not Modify Casually

A golden trace may only change when the runtime event contract intentionally changes.

Allowed reasons:

```text
schema version change
intentional event lifecycle change
intentional payload contract change
bug fix to invalid fixture data
```

Not allowed:

```text
cosmetic edits
renaming without semantic need
adding fields for convenience
changing order to satisfy a fragile test
```

---

### 2. Preserve Lifecycle Semantics

A valid immediate-side trace must preserve:

```text
start first
complete last
single run_id
single goal_id
schema_version = uar.event.v1
```

Failure traces must show failure through event semantics, not by omitting terminal completion.

---

### 3. Volatile Fields Are Not Semantics

The following fields may differ between equivalent traces:

```text
timestamp
correlation_id
generated run_id
generated goal_id
```

They are normalized by the certification layer when appropriate.

---

### 4. Payload Changes Are Semantic

Payload changes are meaningful.

If a payload changes, then one of these must be true:

```text
the runtime behavior changed intentionally
the fixture was wrong
the certification rule was incomplete
```

Do not normalize away payload drift unless there is a documented reason.

---

### 5. Event Order Is Semantic

Event order matters.

Changing:

```text
start -> skill_start -> skill_complete -> complete
```

into another order is a runtime contract change.

---

## Required Checks After Fixture Changes

Run:

```bash
pytest tests/test_runtime_trace_fixtures.py -q
pytest tests/test_replay_certification.py -q
pytest tests/test_timeline.py -q
./scripts/burn_in.sh
```

Expected result:

```text
all pass
```

---

## Review Checklist

Before accepting any golden trace change:

```text
[ ] Why did the trace change?
[ ] Is this a semantic runtime change?
[ ] Are replay tests updated?
[ ] Are certification tests updated?
[ ] Is timeline projection still stable?
[ ] Does docs/BURN_IN_PLAN.md remain true?
[ ] Does SYSTEM.md remain true?
```

---

## Guiding Rule

```text
Golden traces are executable documentation.
```

Treat them like runtime law.
