# UAR Conformance v1.1.0

## Stabilization Mode

UAR modular runtime (`uar/`) is the single authoritative app. UOR
object/runtime/agent endpoints are served by `uar/api/routers/uor.py`,
backed by `uar/objects/` (SQLite-persisted, thread-safe). The previous
`apps/api-python/` reference implementation has been merged in and removed.

## Deterministic-First Runtime

UAR is deterministic-first.

Adaptive planning must remain:

- optional
- explicitly enabled
- observable
- replayable
- bounded by runtime contracts

Execution truth is defined by the RuntimeEvent stream.

## Guarantees

### Object Layer
- Deterministic digest via canonical JSON
- Immutable objects stored and retrievable
- Created objects receive lineage events

### Runtime Layer
- Runtime code must pass AST validation
- Only approved builtins are allowed
- Runtime registry is persisted in SQLite

### Execution Layer
- Execution runs in a subprocess
- Execution is bounded by timeout and memory parameters
- Execution produces:
  - output object
  - execution record
  - lineage entries

### Event Contract Layer
- Runtime events use schema `uar.event.v1`
- Event streams must:
  - start with `start`
  - end with `complete`
  - preserve a single `run_id`
  - preserve a single `goal_id`
- Unknown optional event fields must be ignored by consumers
- Breaking schema changes require a new schema version

### Replay Layer
- RunRecord reconstruction is deterministic
- Event ordering is preserved during replay
- Replay validation rejects malformed streams
- Replay summaries are stable for equivalent event streams

### Workflow Layer
- Steps execute sequentially
- Outputs feed forward into later steps
- Values are normalized for chaining via `values`

### Persistence
- Objects, lineage, and runtimes are stored in SQLite
- Runtime registry survives reload

## Known Gaps
- No DAG execution
- No concurrency safety
- Sandbox is process/resource constrained, not full OS/container isolation
- Modular extraction is partial and not canonical yet
- Event schema migration tooling not yet implemented

## Pass Criteria
- `pytest tests/` passes
- Workflow returns valid output digest
- Lineage trace contains execution events
- Runtime registry persists across reload
- Replay validation passes
- RuntimeEvent streams reconstruct equivalent RunRecords deterministically
- Partial modules do not replace canonical `main.py` until parity is proven