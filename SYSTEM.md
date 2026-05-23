# Universal Agent Runtime (UAR) — System Guide

## Status

UAR is currently in **Foundation → Platform roundout**.

This branch establishes a modular runtime foundation with event-driven execution, replayable run records, API adapters, streaming, release controls, environment configuration, and a staged web control surface. The current priority is production stabilization, not feature expansion.

## Runtime Philosophy

UAR is deterministic-first.

Adaptive or agentic planning is optional, explicitly gated, observable,
and replayable.

The runtime core must remain:

- inspectable
- reproducible
- bounded
- testable
- replay-safe

LLM-assisted orchestration is treated as an optional planning layer above the
runtime substrate, not as the execution truth itself.

## Production Posture

Feature expansion is frozen for this phase.

Do not add new capabilities until the current platform slice is proven by CI, documented, and release-scoped.

Deferred until after stabilization:

- parallel executor expansion
- replay timeline UI
- richer orchestration intelligence
- advanced graph animation
- production database backends beyond JSONL

## Versioning

Versioning is controlled through the root `VERSION` file.

Current release commands:

```bash
make version
make sync-version
make gate
make release
```

Rules:

- `VERSION` is the release source of truth.
- `pyproject.toml` must match `VERSION` before release.
- `make sync-version` updates `pyproject.toml` from `VERSION`.
- `make gate` runs the canonical regression and release verification flow.
- `make release` validates, syncs version, checks release docs for uncommitted drift, creates an annotated git tag, and pushes the tag.
- Tags must use the form `vX.Y.Z`.

## Environment Configuration

Configuration is intentionally lightweight for the foundation release.

See `.env.example`:

```env
API_HOST=127.0.0.1
API_PORT=8000
```

Current runtime defaults:

```text
API_HOST=127.0.0.1
API_PORT=8000
```

The Makefile supports overriding values:

```bash
API_HOST=0.0.0.0 API_PORT=8080 make up
```

Assumption: `.env` loading is not yet automatic. Operators may export variables in the shell or pass them into `make`. A future deployment pass may add a formal config loader if needed.

## Dependency Policy

### Python

Python dependencies are declared in `pyproject.toml`.

Current policy:

- Python dependency ranges are acceptable during foundation development.
- Release validation must pass with the dependency versions resolved by CI.
- Future production hardening may pin exact versions or add a lockfile.

### Node / UI

The web UI is staged and non-blocking for the foundation release.

Current policy:

- UI build may remain a signal rather than a release gate.
- Node dependencies should be pinned before UI becomes release-critical.
- UI must consume API/stream contracts only and must not define runtime semantics.

## System Layers

```text
L0 Contracts
  GoalSpec, StrategySpec, RunRecord, RuntimeEvent

L1 Runtime Core
  planner, executor, registry, replay validation

L2 Skills
  section_sum, doc_ingest, dependency_map, sum_review

L3 Memory
  JSONL run persistence

L4 Adapters
  CLI, FastAPI /run, FastAPI /stream

L5 UI Control Surface
  React UARPanel, React Flow graph surface

L6 Validation / Governance
  pytest, CI, conformance split, production checklist, release process
```

## Dependency Direction Rules

Allowed:

```text
UI -> API -> Runtime Core -> Skills
API -> Memory
CLI -> Runtime Core -> Memory
Tests -> public boundaries
Docs -> all
```

Forbidden:

```text
Runtime Core -> API
Runtime Core -> UI
Skills -> API/UI
Memory -> API/UI
UI -> Python internals
```

## Core Contracts

### GoalSpec

User intent normalized into an executable runtime request.

```python
GoalSpec(
    id: str,
    user_intent: str,
    objective: str,
    constraints: list[str],
    success_criteria: list[str],
    required_skills: list[str],
    metadata: dict,
)
```

### StrategySpec

Planner output. A strategy is a skill sequence, not an execution result.

```python
StrategySpec(
    goal_id: str,
    ordered_skills: list[str],
)
```

### RuntimeEvent

Canonical event unit for execution, streaming, replay, UI, and persistence.

```json
{
  "schema_version": "uar.event.v1",
  "type": "orchestration_plan | start | skill_start | skill_complete | skill_failed | error | complete",
  "run_id": "string",
  "goal_id": "string",
  "skill": "string | null",
  "timestamp": 0.0,
  "payload": {},
  "error": "string | null"
}
```

Event rules:

- `schema_version` is currently `uar.event.v1`.
- Event consumers must ignore unknown optional fields.
- Breaking event changes require a new schema version.
- The stream may emit `orchestration_plan` before `start`.
- The execution event stream must contain `start` and terminal `complete`.

### RunRecord

Durable run artifact reconstructed from the event stream.

```python
RunRecord(
    run_id: str,
    goal_id: str,
    skills: list[str],
    outputs: list,
    status: "pending" | "running" | "completed" | "failed",
    errors: list[str],
    events: list[RuntimeEvent],
    final_context: dict,
)
```

## Execution Model

UAR uses one execution truth:

```text
Executor.iter_events(...) -> RuntimeEvent stream
Executor.run(...)         -> collects iter_events and returns RunRecord
/api/uar/stream           -> serializes RuntimeEvents as SSE
/api/uar/run              -> returns a RunRecord JSON payload
JsonRunStore              -> persists RunRecord artifacts
```
