# UAR Conformance v0.2.1

## Guarantees

### Object Layer
- Deterministic digest via canonical JSON
- Immutable objects stored and retrievable

### Runtime Layer
- Runtime code must pass AST validation
- Only approved builtins allowed

### Execution Layer
- Execution produces:
  - output object
  - execution record
  - lineage entries

### Workflow Layer
- Steps execute sequentially
- Outputs feed forward
- Values normalized for chaining

### Persistence
- Objects, lineage, runtimes stored in SQLite
- Survive restart

## Known Gaps
- No DAG execution
- No concurrency safety
- Sandbox is logical, not OS-isolated

## Pass Criteria
- Smoke test runs successfully
- Workflow returns valid output digest
- Lineage trace contains execution events
