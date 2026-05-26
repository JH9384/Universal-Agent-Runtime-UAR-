# Phase 1 — Runtime Stabilization

## Purpose

Phase 1 establishes UAR as a deterministic event-driven runtime substrate with replayable execution semantics.

This phase freezes the runtime substrate and prioritizes:

- deterministic replay
- replay integrity
- runtime governance
- operational stability
- CI discipline
- streaming validation
- persistence validation

This phase intentionally excludes:

- semantic evaluator systems
- DSE overlays
- memory graph cognition
- symbolic runtime mutation
- autonomous adaptive orchestration

---

# Canonical Runtime Truth

The canonical execution truth of UAR is:

```text
RuntimeEvent stream + RunRecord
```

UI state, metrics, overlays, and observers are downstream consumers and are not runtime truth.

---

# Required Burn-In Validation

## Runtime

- planner routing
- executor correctness
- timeout handling
- retry semantics
- recipe expansion
- replay reconstruction

## Streaming

- SSE lifecycle
- WebSocket lifecycle
- heartbeat behavior
- reconnect handling
- bounded queues

## Persistence

- JSONL replay validation
- interrupted-run recovery
- replay consistency
- corruption handling

## Failure Injection

- malformed inputs
- skill timeouts
- failed recipes
- dropped streams
- unavailable dependencies

---

# Golden Trace Policy

Golden traces are behavioral contracts.

Allowed variance:

- timestamps
- UUID values

Disallowed variance:

- event ordering drift
- replay semantic drift
- RunRecord semantic drift

Fixture updates require explicit review and rationale.

---

# CI Gates

Required runtime gates:

```text
make gate
pytest -q
runtime burn-in
replay integrity validation
streaming validation
```

No feature expansion merges should bypass runtime substrate validation.

---

# Runtime Boundary Freeze

Until Phase 1 stabilization completes, do not merge:

- semantic evaluators
- DSE overlays
- observer cognition layers
- adaptive orchestration systems
- symbolic runtime mutation

All expansion systems must consume RuntimeEvents and RunRecords instead of redefining runtime truth.

---

# Exit Criteria

Phase 1 completes when:

- deterministic replay is stable
- burn-in runs are green
- runtime CI gates are stable
- golden traces are stable
- replay semantics are canonicalized
- runtime substrate is operationally stable

---

# Runtime Identity

```text
UAR v1.x is a deterministic event-driven runtime substrate
with replayable execution semantics.
```
