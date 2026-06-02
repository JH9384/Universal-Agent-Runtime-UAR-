# Universal Agent Runtime (UAR) — System Guide

## Status

UAR is in the **v1.2 Operational Intelligence Platform** phase.

The Trust Spine is complete. All six phases (T1–T6) are operational.
The current mission is **Ω-7B.1 Operational Validation** — proving that
trust metrics behave correctly with real operational data.

```text
Execution -> Evidence -> Trust -> Operations -> Analytics -> Search -> Insight
```

Execution generates evidence. Evidence establishes trust. Trust drives operational
intelligence. Intelligence surfaces actionable operator insight.

### Trust Spine — Complete

| Phase | Status |
|-------|--------|
| T1 Replay Confidence | Complete |
| T2 Runtime Health | Complete |
| T3 Burn-In Framework | Complete |
| T4 Certification Engine | Complete |
| T5 Mission Control | Complete |
| T6 Replay Explorer | Complete |

See [docs/TRUST_SPINE.md](docs/TRUST_SPINE.md) and [docs/operations/LEARNING_MODEL.md](docs/operations/LEARNING_MODEL.md).

## Production Posture

**Feature Freeze: ACTIVE** — Ω-7B.1 Operational Validation in progress.

Do not add new runtime capabilities, autonomy layers, or infrastructure expansions
until Ω-7B.1 exit criteria are met.

Permitted during freeze:

- Bug fixes and correctness patches
- Instrumentation additions
- Documentation updates
- Dashboard visualizations
- Operational validation tooling

Deferred until Ω-7B.1 exit:

- New trust spine phases (none planned — spine is complete)
- New learning logic (architecture frozen)
- New operational intelligence layers (all 12 layers are complete)
- Marketplace systems
- Agent economy systems
- Workflow studio expansion

## Versioning

Versioning is controlled through the root `VERSION` file.

Current release commands:

```bash
make version
make sync-version
make release
```

Rules:

- `VERSION` is the release source of truth.
- `pyproject.toml` must match `VERSION` before release.
- `make sync-version` updates `pyproject.toml` from `VERSION`.
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
  planner, executor, registry, skill registry, replay validation

L2 Skills
  127+ registered skills: STEM, AI/LLM, document, hardware, crypto, blockchain

L3 Memory
  SQLite (primary), Postgres (production), JSONL (legacy), Redis (cache)

L4 Adapters
  CLI, FastAPI /run, FastAPI /stream, WebSocket, SSE, operator routers

L5 UI Control Surface
  React Operator Dashboard: mission control, replay explorer, topology, time machine

L6 Validation / Governance
  pytest (4322 tests), CI, conformance split, production checklist, release process

L7 Trust Spine
  replay confidence, runtime health, burn-in, certification, mission control, replay explorer

L8 Operational Intelligence
  analytics, search, knowledge graph, insight generation, trust-aware ranking
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

### Runtime routes

```text
POST /api/uar/run
POST /api/uar/stream
GET  /api/uar/runs
GET  /api/uar/recipes
```

### Trust Spine routes

```text
GET  /api/uar/replay_confidence/{run_id}
GET  /api/uar/runtime_health
GET  /api/uar/burn_in
GET  /api/uar/certification
GET  /api/uar/mission_control
GET  /api/uar/replay
```

### Operational Intelligence routes

```text
GET  /api/uar/recommendations
GET  /api/uar/recommendations/trust
GET  /api/uar/recommendations/effectiveness
GET  /api/uar/recommendations/quality
GET  /api/uar/insights/patterns
GET  /api/uar/insights/evolution
GET  /api/uar/insights/clusters
GET  /api/uar/insights/intelligence
GET  /api/uar/search
GET  /api/uar/graph
GET  /api/uar/operator/*
```

### Health & metrics

```text
GET  /api/health/live
GET  /api/health/ready
GET  /api/health/dashboard
GET  /api/metrics
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

Current persistence supports three backends:

- **SQLite** (`SqliteRunStore`) — primary embedded store, writer thread + WAL
- **Postgres** (`PostgresRunStore`) — production relational store with async support
- **JSONL** (`JsonRunStore`) — lightweight flat-file, legacy path

All stores implement the `BaseStore` interface.

Appropriate for:

- local development (SQLite)
- production deployment (Postgres)
- debugging and audit logs (JSONL)
- replay validation (all backends)
- complex querying (Postgres / SQLite)
- concurrent writers (Postgres)
- multi-user deployment (Postgres)

Not yet appropriate for:

- event sourcing at very high volume (needs sharding)

Future upgrade path:

```text
SQLite / Postgres -> Event Store (optional, at volume)
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

- UAR 0.1.0 is single-node.
- JSONL persistence is acceptable for local development and early audit logs.
- UI is staged and not required for the core runtime release.
- `uar.event.v1` is stable for the foundation release.
- Conformance tests are useful but do not block foundation release.
- `make release` is intended to run from a clean git working tree.
- A release tag is not valid unless CI has passed.

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
The architecture is finally rich enough that the next improvements should come
from observed behavior rather than design intuition.

STOP BUILDING. START MEASURING.
```
