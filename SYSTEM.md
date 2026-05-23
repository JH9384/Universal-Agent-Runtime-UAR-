# Universal Agent Runtime (UAR) — System Guide

## Status

UAR is currently in **Foundation → Platform roundout**.

This branch establishes a modular runtime foundation with event-driven execution, replayable run records, API adapters, streaming, release controls, environment configuration, and a staged web control surface. The current priority is production stabilization, not feature expansion.

## Runtime Philosophy

UAR is deterministic-first.

Adaptive or agentic planning is optional, explicitly gated, observable, and replayable.

The runtime core must remain:

- inspectable
- reproducible
- bounded
- testable
- replay-safe

LLM-assisted orchestration is treated as an optional planning layer above the runtime substrate, not as the execution truth itself.

## Production Posture

Feature expansion is frozen for this phase.

Do not add new capabilities until the current platform slice is proven by CI, documented, and release-scoped.

Deferred until after stabilization:

- parallel executor expansion
- replay timeline UI beyond the minimal event inspector
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

Runtime configuration defaults are formalized in `uar/core/config.py` as `RuntimeConfig`. Adapters should normalize environment, request, or deployment values into this contract before controlling core runtime behavior.

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
  planner, executor, registry, replay validation, runtime config

L2 Skills
  section_sum, doc_ingest, dependency_map, sum_review

L3 Memory
  JSONL run persistence

L4 Adapters
  CLI, FastAPI /run, FastAPI /stream

L5 UI Control Surface
  React UARPanel, React Flow graph surface, minimal replay timeline

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

Runtime events should be created through canonical builders in:

```text
uar/core/events.py
```

Executor compatibility helpers live in:

```text
uar/core/executor_events.py
```

The runtime currently emits JSON-compatible dictionaries so replay, streaming, persistence, and UI consumers share the same payload shape.

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
- Canonical event builders should be used instead of ad hoc dictionaries.
- Optional metadata such as `correlation_id` must not be required for replay correctness.

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

## Replay Timeline Projection

Replay timeline projection utilities live in `uar/core/timeline.py`.

Current scope:

- project RuntimeEvents into chronological UI-safe timeline entries
- preserve event order through timeline indices
- summarize skill starts, completions, failures, and event counts
- ignore unknown timeline event types without mutating replay truth

The timeline projection layer is intentionally visualization-agnostic. It supports a minimal event inspector first, not advanced cognition overlays.

## Orchestration Model

Orchestration utilities live in `uar/core/orchestrator.py`.

Current scope:

- sequential skill graph manifest
- graph nodes and edges for visualization
- registered/unregistered skill metadata

Deferred:

- true parallel execution
- dependency-aware scheduling
- dynamic replanning

## UI Scope

The web UI is a staged platform surface.

Current purpose:

- submit goals
- consume SSE events
- render execution/orchestration graph
- display event log
- inspect minimal replay timelines

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
- planner router tests
- runtime config tests
- runtime event builder tests
- replay integrity tests
- replay timeline projection tests

Excluded from foundation CI:

- live-server smoke tests
- legacy API conformance tests
- browser click-through tests
- large repo stress tests
- network disconnect/reconnect tests
- observer/DSE/semantic evaluator modules

Legacy/conformance tests live separately under `tests/conformance/`.

## Launch Commands

One-command local runtime launch:

```bash
make up
```

One-command full local launch with staged UI:

```bash
make up-full
```

Foundation validation:

```bash
make validate
```

Canonical release gate:

```bash
make gate
```

GitHub one-click validation:

```text
Actions -> UAR Validation -> Run workflow
```

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

## Explicit Foundation Assumptions

- UAR 1.1.0 is single-node.
- JSONL persistence is acceptable for local development and early audit logs.
- UI is staged and not required for the core runtime release.
- `uar.event.v1` is stable for the foundation release.
- Conformance tests are useful but do not block foundation release.
- `make release` is intended to run from a clean git working tree.
- A release tag is not valid unless CI has passed.
- Other-side modules consume RuntimeEvents and RunRecords; they do not redefine executor truth.

## Production Readiness Gate

Before merging to main, verify:

- foundation Python CI is green
- stream/run parity passes
- no duplicate execution in stream mode
- RuntimeEvent contract tests pass
- replay reconstruction tests pass
- runtime config tests pass
- timeline projection tests pass
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

## Other-Side Boundary

Observer systems, DSE overlays, semantic evaluators, memory graph cognition, symbolic overlays, and multi-agent orchestration are explicitly outside this immediate stabilization slice.

Those modules may attach later through stable runtime outputs:

```text
RuntimeEvents -> RunRecord -> replay timeline -> external observers
```

They must consume the runtime substrate, not redefine it.
