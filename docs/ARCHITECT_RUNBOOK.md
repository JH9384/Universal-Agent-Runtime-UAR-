# Architect Runbook

## Phase 1: Stabilization
- Run: pytest tests/
- Fix all failures
- Confirm execution, workflow, lineage

## Phase 2: Controlled Refactor
- Extract one module at a time
- Run tests after each change

## Phase 3: Cutover
- Only after parity
- Replace main entrypoint

## Rules
- No new features during stabilization
- Tests define truth
