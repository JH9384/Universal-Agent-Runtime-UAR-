# UAR Golden Trace Policy

## Purpose

Golden traces are canonical runtime event traces used to prove that replay, timeline projection, certification behavior, and baseline visualization paths remain stable during burn-in.

They are behavioral contracts, not casual sample data.

---

## Current Golden Traces

```text
tests/fixtures/runtime_trace_success.json
tests/fixtures/runtime_trace_failure.json
```

These traces define the minimum stable lifecycle shapes for successful and failed execution.

---

## Accepted Baseline Scope

Current main-line expansions are accepted into burn-in baseline, including:

```text
runtime replay and certification tests
runtime timeline projection
math_plot skill and tests
3D/data visualization updates
web MathPlotVisualizer and UARPanel integrations
```

These are now part of the current baseline and must be stabilized rather than treated as out-of-scope drift.

---

## Golden Trace Rules

A golden trace may only change when the runtime event contract intentionally changes.

Allowed reasons:

```text
schema version change
intentional event lifecycle change
intentional payload contract change
bug fix to invalid fixture data
accepted baseline visualization path requires documented trace support
```

Not allowed:

```text
cosmetic edits
renaming without semantic need
adding fields for convenience
changing order to satisfy a fragile test
```

---

## Required Checks After Fixture Changes

Run:

```bash
pytest tests/test_runtime_trace_fixtures.py -q
pytest tests/test_replay_certification.py -q
pytest tests/test_timeline.py -q
./scripts/burn_in.sh
```

---

## Review Checklist

```text
[ ] Why did the trace change?
[ ] Is this a semantic runtime change?
[ ] Are replay tests updated?
[ ] Are certification tests updated?
[ ] Is timeline projection still stable?
[ ] Does docs/BURN_IN_PLAN.md remain true?
[ ] Does docs/RUNTIME_BASELINE.md remain true?
```

---

## Guiding Rule

```text
Golden traces are executable documentation.
```
