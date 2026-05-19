# UAR Truth Gates

This file defines what must be true before UAR claims a capability.

## Gate 1 — Runs Locally

A capability is not real until it can be run locally with:

```bash
uvicorn uar.api.server:app --reload
```

## Gate 2 — Has an Invariant

A capability must have at least one test in `tests/` proving its behavior.

## Gate 3 — Has a User Path

A capability must be explainable in docs with:

- what it does
- how to call it
- what output means
- what can fail

## Gate 4 — Has Known Limits

Every capability must state what it does not guarantee.

## Gate 5 — Survives Refactor

A capability is stable only after it still works after module extraction.

## Current Truth Status

| Capability | Real? | Notes |
|---|---:|---|
| Object creation | Yes | Covered by invariant tests |
| Digest verification | Yes | Covered by invariant tests |
| Runtime registry | Yes | Covered by invariant tests |
| Execution | Yes, prototype | Bounded subprocess execution |
| Workflow chaining | Yes, linear only | DAG not implemented |
| Lineage | Yes | Basic event trace |
| Modular architecture | Partial | `main.py` remains canonical |
| Production security | No | Process sandbox only, not container/VM |

## Rule

If a capability fails one of these gates, describe it as experimental, partial, or planned — never complete.
