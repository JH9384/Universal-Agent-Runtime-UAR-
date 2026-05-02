# Universal Agent Runtime (UAR) — System Guide

## Status

UAR is currently in **Foundation → Platform roundout**.

This branch establishes a modular runtime foundation with event-driven execution, replayable run records, API adapters, streaming, and a staged web control surface. The current priority is production stabilization, not feature expansion.

## Production Posture

Feature expansion is frozen for this phase.

Do not add new capabilities until the current platform slice is proven by CI, documented, and release-scoped.

Deferred until after stabilization:

- parallel executor expansion
- replay timeline UI
- advanced agent reasoning
- richer orchestration intelligence
- advanced graph animation

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
  pytest, CI, conformance split, production checklist
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

The event stream is primary. `RunRecord` is a derived durable artifact.

## API Surface

Current foundation routes:

```text
POST /api/uar/run
POST /api/uar/stream
GET  /api/uar/runs
```

Suggested external versioned routes for future public clients:

```text
POST /api/v1/uar/run
POST /api/v1/uar/stream
GET  /api/v1/uar/runs
```

## Streaming Contract

SSE framing is transport only. Each `data:` payload is a `RuntimeEvent`.

Example:

```text
event: skill_start
data: {"schema_version":"uar.event.v1", ...}
```

Expected high-level sequence:

```text
orchestration_plan   optional platform graph metadata
start                execution start
skill_start          skill begins
skill_complete       skill succeeds
skill_failed         skill fails
complete             terminal run state
```

## Replay Model

Replay utilities live in `uar/core/replay.py`.

Responsibilities:

- validate RuntimeEvent shape
- enforce event schema version
- enforce event stream lifecycle
- reconstruct RunRecord without re-execution
- summarize replayed run records

Principle:

```text
events = truth
RunRecord = reconstruction
```

## Orchestration Model

Orchestration utilities live in `uar/core/orchestrator.py`.

Current scope:

- sequential skill graph manifest
- graph nodes and edges for visualization
- registered/unregistered skill metadata

Deferred:

- true parallel execution
- dependency-aware scheduling
- agent reasoning
- dynamic replanning

## UI Scope

The web UI is a staged platform surface.

Current purpose:

- submit goals
- consume SSE events
- render execution/orchestration graph
- display event log

Production stance:

- UI must not control runtime semantics.
- UI consumes API/stream contracts only.
- UI can be staged separately from runtime foundation if TypeScript build is not release-ready.

## Memory Scope

Current persistence is append-only JSONL via `JsonRunStore`.

Appropriate for:

- local development
- debugging
- replay validation
- early audit logs

Not yet appropriate for:

- concurrent writers
- multi-user deployment
- transactional guarantees
- complex querying

Future upgrade path:

```text
JsonRunStore -> SQLiteRunStore -> Postgres/Event Store
```

## Validation Strategy

Foundation CI should validate deterministic runtime behavior only.

Included in foundation CI:

- runtime pipeline tests
- API TestClient tests
- streaming contract tests
- run/stream parity tests
- persistence tests
- security/path tests
- timeout behavior tests
- CLI smoke tests

Excluded from foundation CI:

- live-server smoke tests
- legacy API conformance tests
- browser click-through tests
- large repo stress tests
- network disconnect/reconnect tests

Legacy/conformance tests live separately under `tests/conformance/`.

## Local Development

Install Python runtime:

```bash
python -m pip install -e '.[dev]'
pytest tests/test_*.py
```

Run API locally:

```bash
uvicorn uar.api.server:app --reload
```

Run web UI:

```bash
cd apps/web
npm install
npm run dev
```

Manual stream check:

```bash
curl -N -X POST http://localhost:8000/api/uar/stream \
  -H "Content-Type: application/json" \
  -d '{"goal":"stream test","skills":["section_sum"]}'
```

## Production Readiness Gate

Before merging to main, verify:

- foundation Python CI is green
- stream/run parity passes
- no duplicate execution in stream mode
- RuntimeEvent contract tests pass
- replay reconstruction tests pass
- UI is either green or explicitly staged
- dependencies are pinned or consciously accepted as pre-release/staged
- release slice strategy is chosen
- PR is either split or accepted as an integration merge

## Management Cycle

```text
Plan     complete
Build    sufficient for current platform slice
Check    active until CI is green
Control  active through contract tests and release scope
Release  blocked until production checklist is satisfied
```

## Guiding Rule

```text
No more expansion until existing behavior is proven, documented, and releasable.
```
