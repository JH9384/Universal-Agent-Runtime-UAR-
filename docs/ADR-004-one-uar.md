# ADR-004: One UAR — UOR consolidation

- Status: Accepted
- Date: 2026-05-19
- Supersedes: None

## Context

The repository previously contained two FastAPI applications:

1. **Canonical app** — `uar/api/server.py`, the production runtime
   referenced by `Dockerfile.prod`, `docker-compose.prod.yml`, the
   `Makefile`, `boot.sh`, and `start.sh`. It exposes the skills/recipes
   pipeline, run streaming, the document library, and the React UI.
2. **UOR reference app** — `apps/api-python/main.py` (1024 LOC) plus a
   parallel `apps/api-python/uar/` package with its own `agents`,
   `state`, `store`, `sandbox`, `models`, and `skills/atomic_lang_model`
   modules. It served the UOR Foundation conformance contract:
   content-addressed objects (`/objects`), lineage tracing
   (`/agents/lineage/trace`), AST-validated subprocess runtimes
   (`/runtimes/*`, `/agents/execution/run`), and supporting agent verbs
   (locator, verifier, composer, workflow, constraint, bridge,
   inference, delegation, atomic_lang_model).

The two-app split caused:

- **Confusing imports** — both apps shadowed the package name `uar`.
- **Duplicate `atomic_lang_model.py`** — one as a class-style HTTP
  client, one as pipeline-style skill functions.
- **Conformance tests gated** — `tests/conformance/test_invariants.py`
  was permanently `pytest.mark.skip` because it depended on the
  duplicate.
- **No single source of truth** — UOR-related untracked work
  (`uor_integration.py`, `atlas_embeddings.py`, etc.) was being added
  to the canonical app while UOR endpoints lived elsewhere.

## Decision

There is **one UAR**. The UOR reference app has been merged into the
canonical app:

| Concern | Location |
| --- | --- |
| Object/lineage/runtime store (SQLite + thread-safe in-memory mirror) | `uar/objects/store.py` |
| AST-validated subprocess sandbox | `uar/objects/sandbox.py` |
| Pydantic v2 request models | `uar/objects/models.py` |
| Capability map for `/agents/constraint/check` | `uar/objects/agents.py` |
| Service helpers (digest, create_record, register_runtime, execute_runtime, workflow_run, locator/inference/bridge/delegation) | `uar/objects/service.py` |
| ALM HTTP client class | `uar/objects/alm_client.py` |
| FastAPI router mounting all UOR endpoints | `uar/api/routers/uor.py` |
| Conformance tests | `tests/conformance/test_invariants.py` (now active) |

The router is mounted from `uar/api/server.py`. The default
`ObjectStore` is lazily constructed against `UOR_DB_PATH` (or the legacy
`DB_PATH`); tests inject their own via `app.dependency_overrides`.

The directory `apps/api-python/` has been deleted along with all
references in docs and tooling.

## Consequences

**Positive**
- Single FastAPI app, single `uar/` package, single `pip install -e .`.
- Conformance tests are no longer gated and pass: 10/10 invariants
  green against the merged app.
- SQLite store is now thread-safe (`threading.RLock` around the
  in-memory mirror, WAL mode on the connection).
- ALM HTTP client and pipeline skill coexist cleanly under different
  modules without name collisions.

**Trade-offs**
- The default `ObjectStore` is a process-wide singleton constructed on
  first use; tests must reset via dependency override (documented in
  the conformance tests).
- The DB path defaults to `./uar.sqlite3` in the working directory; in
  Docker, set `UOR_DB_PATH=/var/lib/uar/uor.sqlite3`.
- Existing on-disk `uar.sqlite3` files from the deleted app continue to
  work (same schema).

## Validation

- `pytest tests/` → 191 pass / 1 fail (pre-existing
  `test_governance_system_budget_check`) / 7 skip.
- `pytest tests/conformance/` → 10/10 pass.
- All UOR routes register on `app`: `/objects`, `/runtimes`,
  `/runtimes/register`, `/runtimes/seed`, `/runtimes/{name}`, `/agents`,
  `/agents/locator/query`, `/agents/verifier/{verify,compare}`,
  `/agents/composer/compose`, `/agents/execution/run`,
  `/agents/workflow/run`, `/workflows/run`, `/agents/lineage/trace`,
  `/agents/constraint/check`, `/agents/bridge/ingest`,
  `/agents/inference/analyze`, `/agents/delegation/plan`,
  `/agents/atomic_lang_model/{analyze,generate,verify}`.
