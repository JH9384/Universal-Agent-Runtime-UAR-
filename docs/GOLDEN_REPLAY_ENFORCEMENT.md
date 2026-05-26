# Golden Replay Enforcement

## Purpose

Golden replay enforcement defines the deterministic certification boundary for UAR.

The objective is:

```text
same inputs
same events
same outputs
same ordering
```

under certified runtime conditions.

---

# Replay Enforcement Goals

## Phase 1

Validate:

- RuntimeEvent schema compatibility
- event ordering
- replay legality
- side-effect legality
- deterministic certification metadata

## Phase 2

Validate:

- deterministic payload equivalence
- event-stream hashing
- replay drift detection
- runtime timing tolerance windows
- compatibility version enforcement

## Phase 3

Validate:

- distributed replay equivalence
- orchestrated replay legality
- cross-runtime consistency
- scheduler determinism

---

# Replay Failure Conditions

Replay certification must fail on:

- schema mismatch
- missing required events
- invalid ordering
- replay-unsafe skill execution
- destructive side effects
- incompatible RuntimeEvent versions
- run_id drift
- goal_id drift

---

# CI Governance Direction

CI should eventually reject:

- ReplayUnsafe skills in deterministic workflows
- invalid RuntimeEvent schema changes
- non-versioned event contract changes
- replay drift
- event ordering regressions

---

# Strategic Position

Replay certification is foundational infrastructure.

Agent orchestration must never outrun deterministic governance.
