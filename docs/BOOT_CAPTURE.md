# UAR Boot & API Capture

> Captured live from UAR **v1.1.0** (aligned with UOR v0.5.2) on 2026-05-29.  
> All output is real — server booted, endpoints hit, responses recorded verbatim.

---

## 1. Boot sequence

### Starting the API server

```bash
# Minimal — API only (port 8000)
./start.sh

# Full-stack — API + React web UI + auto-open browser
./boot.sh

# Makefile shorthands
make up           # install + api
make up-full      # install + api + web UI (parallel)
make api          # uvicorn only (assumes .venv already installed)
```

`boot.sh` waits for `GET /api/health` to return 200 before declaring success
and opening the browser. Both API and web PIDs are trapped for clean `Ctrl+C`
shutdown.

### Boot log (actual server output)

```
2026-05-27 07:55:10,618 - uar.api.server - INFO - Booting UAR 1.1.0 (aligned with UOR v0.5.2)
2026-05-27 07:55:10,844 - root - WARNING - Unstructured not available. Install with: pip install unstructured[local-inference]
2026-05-27 07:55:10,844 - root - WARNING - Docling not available. Install with: pip install docling
2026-05-27 07:55:10,848 - uar.core.recipes - INFO - All recipe skills validated successfully
INFO:     Started server process [72157]
INFO:     Waiting for application startup.
2026-05-27 07:55:10,943 - uar.api.server - INFO - UAR API starting up...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

The two `WARNING` lines are expected on lean installs — `unstructured` and
`docling` are optional heavy dependencies for enhanced document ingestion.

---

## 2. Health endpoints

### `GET /api/health` — liveness

```bash
curl http://127.0.0.1:8000/api/health
```

```json
{
    "status": "healthy",
    "version": "1.1.0",
    "uor_upstream_version": "v0.5.2"
}
```

### `GET /api/health/ready` — readiness (Kubernetes probe)

```bash
curl http://127.0.0.1:8000/api/health/ready
```

```json
{
    "status": "ready",
    "checks": {
        "skills_loaded": true,
        "disk_writable": true,
        "ollama_reachable": true,
        "redis_reachable": null,
        "circuit_breakers": true,
        "open_circuits": []
    }
}
```

| Check | Meaning |
|---|---|
| `skills_loaded` | Registry populated (≥1 skill registered) |
| `disk_writable` | `RUNS_DIR` is writeable (unique temp-file probe per concurrent call) |
| `ollama_reachable` | `GET $OLLAMA_HOST/api/tags` returned 2xx |
| `redis_reachable` | `null` = Redis not configured; `true/false` when `REDIS_URL` is set |
| `circuit_breakers` | No external-service circuit is currently open |
| `open_circuits` | List of open circuit-breaker names (empty = all closed) |

### `GET /api/health/live` — minimal k8s liveness

```bash
curl http://127.0.0.1:8000/api/health/live
# {"status":"alive"}
```

---

## 3. Executing a run

### `POST /api/uar/run` — synchronous run

```bash
curl -X POST http://127.0.0.1:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"sum the values [10, 20, 30]","skills":["section_sum"]}'
```

**Response (truncated for clarity):**

```json
{
    "run_id": "1b6e1475-0f98-448b-b97f-575fbf7ef238",
    "goal_id": "api-de71ce28",
    "skills": ["section_sum"],
    "outputs": [
        {
            "section_sum": {
                "summary": "Processed goal: sum the values [10, 20, 30]"
            }
        }
    ],
    "status": "completed",
    "errors": [],
    "final_context": {
        "section_sum": {
            "summary": "Processed goal: sum the values [10, 20, 30]"
        }
    }
}
```

Every event in the `events` array carries:

| Field | Description |
|---|---|
| `schema_version` | Always `"uar.event.v1"` |
| `type` | `start` → `skill_start` → `skill_complete` → `metrics` → `complete` |
| `run_id` | UUID for this execution |
| `goal_id` | Stable short ID derived from the goal text |
| `uor_address` | `sha256:…` content-address of the event payload |
| `uor_witness` | Fingerprint + verified label for audit trail |

### Event lifecycle

```
start
  └─ skill_start   (per skill)
  └─ skill_complete (per skill)
metrics
complete
```

On failure the chain becomes:
```
start
  └─ skill_start
  └─ skill_failed
error
complete (status: "failed")
```

### `POST /api/uar/stream` — SSE streaming

```bash
curl -N -X POST http://127.0.0.1:8000/api/uar/stream \
  -H "Content-Type: application/json" \
  -d '{"goal":"...","skills":["section_sum"]}'
# Emits: data: {...}\n\n  per event
```

---

## 4. Skills registry

### `GET /api/uar/skills`

```bash
curl http://127.0.0.1:8000/api/uar/skills
```

Returns 127 registered skills at boot (all built-in). Full alphabetical list:

```
agent_workflow, airflow_dag, alm_analyze, alm_generate, alm_verify,
anthropic_chat, anthropic_completion, anthropic_embedding, anunix_health,
anunix_run, auto_down, auto_status, auto_up, autogluon_ml,
autonomi_download, autonomi_status, autonomi_upload, bio_compute,
blackboard_message, blackboard_status, budget_status, cern_root,
chem_analysis, chromadb_store, cipher_ops, crewai_task, crewai_workflow,
crypto_analyze, dagster_pipeline, dagster_status, data_viz_3d,
dbt_transform, dependency_map, deps, diff_eq_solve, doc_ingest,
doc_ingest_enhanced, eco_canon, eco_foundation, eco_status, face_recognize,
flaml_auto, flexible_graphrag, fpga_verify, gemini_chat, gemini_completion,
gemini_embedding, gr_full, gr_index, gr_query, graphrag_index,
graphrag_init, graphrag_query, groq_chat, groq_completion, groq_embedding,
guardrail_check, hologram_query, hologram_status, huggingface_chat,
huggingface_completion, huggingface_embedding, kubeflow_pipe,
llamaindex_query, llamaindex_rag, lm_studio_chat, lm_studio_completion,
lm_studio_embedding, math_compute, micropython, mistral_chat,
mistral_completion, mistral_embedding, mlflow_deploy, mlflow_track,
model_reg, molecular_visualization, moltbook_list, moltbook_post,
moltbook_search, myhdl_design, nft_mint, ollama_generate, openai_chat,
openai_completion, openai_embedding, opencv_process, optuna_tune,
osint_recon, pentest_scan, physics_compute, platformio, prism_btc_anchor,
prism_btc_verify, pycaret_ml, quantum_circuit,
quantum_circuit_visualization, quantum_ml, relativity, review, riscv_cycle,
riscv_sim, scipy_opt, section_sum, security_audit, severance_infer,
severance_verify, smart_contract, snowflake_etl, solana_tx, spark_process,
sum_review, together_chat, together_completion, together_embedding,
trefoil_simulation, uor_addr_canonicalize, uor_addr_resolve,
uor_ecosystem_status, uor_foundation_verify, verilator_sim, verilog_parse,
video_analyze, yolo_detect
```

Skills that require optional dependencies (e.g. `anthropic`, `crewai`,
`autonomi`, `chromadb`) will return a graceful error payload when their
dependency is not installed — they do not crash the server.

---

## 5. Recipes

### `GET /api/uar/recipes`

11 built-in recipes at boot:

| ID | Label | Skills |
|---|---|---|
| `review` | � Ollama review | `doc_ingest`, `ollama_generate` |
| `deps` | 🕸️ Dep map | `doc_ingest`, `dependency_map`, `sum_review` |
| `gr_index` | 📚 GraphRAG index | `graphrag_index` |
| `gr_query` | 🔎 GraphRAG query | `graphrag_query` |
| `gr_full` | ⚡ Full pipeline | `graphrag_index`, `graphrag_query` |
| `auto_up` | ☁️ Autonomi upload | `autonomi_upload` |
| `auto_down` | ☁️ Autonomi download | `autonomi_download` |
| `auto_status` | ☁️ Autonomi status | `autonomi_status` |
| `eco_status` | 🌐 Ecosystem status | `uor_ecosystem_status` |
| `eco_canon` | 🌐 Canonicalize | `uor_addr_canonicalize` |
| `eco_foundation` | 🌐 Foundation verify | `uor_foundation_verify` |

Recipes can be composed with individual skills in a single run via
`execution_order` in the request body.

---

## 6. Run history

### `GET /api/uar/runs` — list all runs

```bash
curl http://127.0.0.1:8000/api/uar/runs
```

Returns an array of full run records (same schema as `/api/uar/run`
response). The backing store is selected at startup:

| Env var | Store used |
|---|---|
| `UAR_DATABASE_URL` set | `PostgresRunStore` |
| `UAR_DATABASE_URL` unset | `JsonRunStore` (JSONL flat file) |

### `GET /api/uar/runs/{run_id}/timeline`

Returns a replay-summary for a single run:

```json
{
    "run_id": "...",
    "goal_id": "...",
    "status": "completed",
    "skills": ["section_sum"],
    "skill_count": 1,
    "event_count": 5,
    "errors": [],
    "outputs": [...]
}
```

---

## 7. Cache & Sandbox

### `GET /api/cache/stats`

```json
{
    "size": 0,
    "maxsize": 1024,
    "skills": []
}
```

Cache warms on first skill execution and respects `UAR_SKILL_CACHE_TTL`
(default: 300 s).

### `GET /api/sandbox/health`

```json
{
    "wasmtime_available": false,
    "wasm_evaluator_active": false,
    "engine_initialized": false,
    "memory_pages": 1
}
```

`wasmtime_available: false` is expected on standard installs — WASM is an
optional hardening path. The sandbox always falls back to the Python AST
evaluator regardless.

---

## 8. Full route map

77 routes registered at boot:

```
GET    /agents
POST   /agents/atomic_lang_model/analyze
POST   /agents/atomic_lang_model/generate
POST   /agents/atomic_lang_model/verify
POST   /agents/bridge/ingest
POST   /agents/composer/compose
POST   /agents/constraint/check
POST   /agents/delegation/plan
POST   /agents/execution/run
POST   /agents/inference/analyze
GET    /agents/lineage/trace
POST   /agents/locator/query
POST   /agents/verifier/compare
POST   /agents/verifier/verify
POST   /agents/workflow/run
POST   /api/advanced/crewai/agent
GET    /api/advanced/crewai/status
POST   /api/advanced/crewai/workflow
POST   /api/advanced/dagster/pipeline
GET    /api/advanced/dagster/status
POST   /api/advanced/governance/budget
GET    /api/advanced/governance/budget/{agent_id}
GET    /api/advanced/governance/status
GET    /api/advanced/governance/violations
POST   /api/advanced/graphrag/query
GET    /api/advanced/graphrag/status
GET    /api/advanced/orchestrator/status
POST   /api/cache/invalidate
GET    /api/cache/stats
GET    /api/health
GET    /api/health/circuit-breakers          (authenticated)
POST   /api/health/circuit-breakers/{service_name}/reset
GET    /api/health/dashboard                 (authenticated)
GET    /api/health/live
GET    /api/health/ready
GET    /api/metrics                          (METRICS_API_KEY if set)
GET    /api/metrics/json                     (METRICS_API_KEY if set)
GET    /api/provenance/{run_id}
POST   /api/sandbox/eval
GET    /api/sandbox/health
GET    /api/status
GET    /api/uar/docs/browse
POST   /api/uar/docs/create_folder
GET    /api/uar/docs/library
DELETE /api/uar/docs/library
GET    /api/uar/docs/presets
POST   /api/uar/docs/upload
POST   /api/uar/query-code
GET    /api/uar/recipes
POST   /api/uar/recipes
PUT    /api/uar/recipes/{recipe_id}
DELETE /api/uar/recipes/{recipe_id}
POST   /api/uar/run
GET    /api/uar/runs
POST   /api/uar/runs/bulk-delete
GET    /api/uar/runs/{run_id}/compare/{other_run_id}
GET    /api/uar/runs/{run_id}/timeline
GET    /api/uar/skills
GET    /api/uar/skills/ping
POST   /api/uar/stream
GET    /api/uar/stream/ws
GET    /ecosystem/status
GET    /metrics
POST   /objects
GET    /objects
POST   /objects/{digest}/content
GET    /objects/{digest}/download
GET    /runtimes
POST   /runtimes/register
POST   /runtimes/seed
GET    /runtimes/{name}
POST   /workflows/run
GET    /ws/run
```

Interactive API docs: `http://127.0.0.1:8000/docs` (Swagger UI)  
OpenAPI schema: `http://127.0.0.1:8000/openapi.json`

---

## 9. Authentication

Pass `X-API-Key: <key>` on requests that require authentication. The default
development key is `dev_key` (configured via `API_KEYS=dev_key:dev:admin`).

```bash
curl -H "X-API-Key: dev_key" http://127.0.0.1:8000/api/health/circuit-breakers
```

**Never ship the default key in production.** Generate a new one with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

## 10. Environment quick-reference

| Variable | Default | Purpose |
|---|---|---|
| `API_HOST` | `127.0.0.1` | Bind address |
| `API_PORT` | `8000` | Listen port |
| `API_KEYS` | `dev_key:dev:admin` | Comma-separated `key:user:tier` |
| `SECRET_KEY` | *(must set)* | JWT / session secret |
| `RUNS_DIR` | `runs` | Run record storage directory |
| `UAR_DATABASE_URL` | *(unset)* | Postgres URL — activates `PostgresRunStore` |
| `REDIS_URL` | *(unset)* | Enables distributed rate limiting |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama endpoint |
| `LOG_LEVEL` | `info` | Uvicorn / app log level |
| `ENVIRONMENT` | `development` | `production` tightens CORS + disables debug |
| `CORS_ORIGINS` | `localhost:3000,5173` | Comma-separated allowed origins |
| `RATE_LIMIT_ENABLED` | `true` | Toggle sliding-window rate limiter |
| `UAR_GC_THRESHOLD` | `50` | GC hint after runs with N+ events |
| `UAR_CONTEXT_DISK_OVERFLOW` | `false` | Spill `PipelineContext` events to disk |
| `UAR_HIERARCHICAL_EXECUTION` | `false` | Recipe nested-execution mode |
| `BACKPRESSURE_ENABLED` | `true` | Adaptive SSE backpressure |
| `SHUTDOWN_GRACE_SECONDS` | `30` | Grace period for connection drain |
| `METRICS_ENABLED` | `true` | Enable metrics collection |
| `METRICS_PORT` | `9090` | Prometheus metrics port |
| `UAR_ENABLE_UOR_EXTENSIONS` | `false` | Enable optional UOR extensions |
| `UOR_DB_PATH` | `uar.sqlite3` | UOR object store path |
| `SECURITY_HEADERS` | unset | Set to `enabled` for security headers |
| `UAR_GZIP_MIN_SIZE` | `1024` | Minimum response size for GZip (bytes) |

Copy `.env.example` to `.env` and edit before first run.
