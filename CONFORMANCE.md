# UAR Conformance v0.2.2

## Stabilization Mode

UAR modular runtime (`uar/`) is authoritative. All conformance invariants pass (81/81). `apps/api-python/main.py` is deprecated and will be removed.

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

## Pass Criteria
- `pytest tests/` passes
- Workflow returns valid output digest
- Lineage trace contains execution events
- Runtime registry persists across reload
- Partial modules do not replace canonical `main.py` until parity is proven
