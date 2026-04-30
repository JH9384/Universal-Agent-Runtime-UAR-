# Recovery and Modularization Plan

## Current Recovery Decision

The branch `ui/real-web-system` contains an invalid `apps/api-python/main.py` caused by uncontrolled whole-file replacement.

This recovery branch was created from known-good `main` to preserve a runnable backend while hardening proceeds.

## Non-Negotiable Rule

No direct whole-file replacement of core backend files.

Workflow:

```text
known-good backend → add tests/guards → extract one module → smoke test → repeat
```

## Protected Backend Files

- `apps/api-python/main.py`
- `apps/api-python/objects.py`
- `apps/api-python/runtime.py`
- `apps/api-python/sandbox.py`
- `apps/api-python/lineage.py`
- `apps/api-python/llm.py`
- `apps/api-python/uor_bridge.py`
- `apps/api-python/schema.py`
- `apps/api-python/proof_objects.py`

## Modularization Sequence

### Phase 1 — Add guardrails only

- Destructive diff guard
- Backend smoke tests
- PR checklist
- CODEOWNERS

No behavior changes.

### Phase 2 — Extract read-only helpers

- `schema.py`
- `uor_bridge.py`
- `proof_objects.py`

No `main.py` behavior removal.

### Phase 3 — Extract runtime internals

- `sandbox.py`
- `objects.py`
- `lineage.py`
- `runtime.py`

Each extraction must keep existing endpoints passing.

### Phase 4 — Add proof/signature endpoints

Only after Phase 1-3 smoke tests pass.

## Smoke Test Gate

Required after every phase:

```text
GET /health
POST /objects
GET /runtimes
POST /agents/execution/run
GET /agents/lineage/trace
```

## Success Criteria

- `main.py` remains runnable at every commit.
- Each module extraction is reversible.
- CI catches destructive deletions.
- No proof/LLM/UOR additions are merged until baseline smoke tests pass.
