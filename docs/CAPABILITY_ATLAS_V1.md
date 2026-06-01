# UAR Capability Atlas v1

> Canonical map of what exists, where it lives, and who consumes it.
> Generated: 2026-06-01

---

## 1. Execution

### 1.1 Executor
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Skill dispatch | `uar/core/executor.py` | `POST /api/uar/run` | `UARPanel` | ✅ |
| Recipe expansion | `uar/core/executor.py` | `POST /api/uar/run` | `RecipeTimeline` | ✅ |
| Retry logic | `uar/core/executor.py` | internal | — | ✅ |
| Parallel skill execution | `uar/core/executor.py` | internal | — | ✅ |
| Circuit breaker integration | `uar/core/executor.py` | internal | — | ✅ |
| Event emission | `uar/core/executor.py` | `POST /api/uar/run` (SSE) | Event stream | ✅ |
| Coalescing lock | `uar/core/executor.py` | internal | — | ✅ |
| Recipe cache | `uar/core/executor.py` | internal | — | ✅ |

### 1.2 Planner
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| SimplePlanner | `uar/core/planner.py` | internal | — | ✅ |
| Goal building | `uar/api/goal_builder.py` | `POST /api/uar/run` | Goal input | ✅ |
| Execution order | `uar/api/goal_builder.py` | `POST /api/uar/run` | `ExecutionOrder` | ✅ |

### 1.3 Recipes
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Recipe registry | `uar/core/recipes.py` | `GET /api/uar/recipes` | `UARPanel` | ✅ |
| Recipe validation | `uar/core/recipes.py` | internal | — | ✅ |
| Nested recipes | `uar/core/recipes.py` | `POST /api/uar/run` | `ExecutionOrder` | ✅ |

---

## 2. Stores

### 2.1 Interface
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| BaseStore (abstract) | `uar/memory/base_store.py` | internal | — | ✅ |
| RunRecord model | `uar/memory/base_store.py` | internal | — | ✅ |
| Metadata ops | `uar/memory/base_store.py` | internal | — | ✅ |

### 2.2 Implementations
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| SQLite (primary) | `uar/memory/sqlite_store.py` | internal | — | ✅ |
| PostgreSQL | `uar/memory/postgres_store.py` | internal | — | ✅ |
| JSONL (replay) | `uar/memory/json_store.py` | internal | — | ✅ |
| Async SQLite writer | `uar/memory/sqlite_store.py` | internal | — | ✅ |
| Async PostgreSQL | `uar/memory/postgres_store.py` | internal | — | ✅ |

### 2.3 Data Model
| Field | SQLite | Postgres | JSONL |
|-------|--------|----------|-------|
| run_id | ✅ | ✅ | ✅ |
| goal_id | ✅ | ✅ | ✅ |
| status | ✅ | ✅ | ✅ |
| skills | ✅ | ✅ | ✅ |
| events | ✅ | ✅ | ✅ |
| result | ✅ | ✅ | ✅ |
| created_at | ✅ | ✅ | ✅ |
| metadata | ✅ | ✅ | ✅ |
| uor_address | ✅ | ✅ | ✅ |
| uor_witness | ✅ | ✅ | ✅ |

---

## 3. Streaming

| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Server-Sent Events (SSE) | `uar/api/routers/streaming.py` | `GET /api/uar/stream` | Event log | ✅ |
| WebSocket | `uar/api/routers/streaming.py` | `WS /api/uar/ws` | `UARPanel` (optional) | ✅ |
| Backpressure | `uar/api/routers/streaming.py` | internal | — | ✅ |
| Heartbeat | `uar/api/routers/streaming.py` | SSE/WS | — | ✅ |
| Event buffer | `uar/api/state.py` | internal | — | ✅ |
| Connection limit | `uar/api/state.py` | internal | — | ✅ |

---

## 4. Skills

### 4.1 Registry
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Skill registration | `uar/core/registry.py` | `GET /api/uar/skills` | `SkillSelector` | ✅ |
| Skill discovery | `uar/core/registry.py` | `GET /api/status` | `SkillGuide` | ✅ |
| Health check | `uar/core/registry.py` | `GET /api/health/dashboard` | `HealthDashboard` | ✅ |

### 4.2 Skill Families (38+ registered)
| Family | Examples | Module |
|--------|----------|--------|
| Document Ingest | `doc_ingest`, `doc_ingest_enhanced` | `uar/skills/doc_ingest.py` |
| Code Analysis | `dependency_map`, `code_analysis` | `uar/skills/code_analysis.py` |
| Math / Plot | `math_compute`, `math_plot`, `math_plot_3d` | `uar/skills/math_*.py` |
| Physics | `physics_compute` | `uar/skills/physics_compute.py` |
| Quantum | `quantum_circuit`, `quantum_ml` | `uar/skills/quantum_*.py` |
| RISC-V | `riscv_sim`, `riscv_cycle` | `uar/skills/riscv_sim.py` |
| Verilog / FPGA | `verilator_sim`, `fpga_build` | `uar/skills/verilog_*.py` |
| Machine Learning | `ml_tools`, `mlops_security` | `uar/skills/ml_*.py` |
| LLM | `ollama_generate`, `anthropic_skills`, `gemini_skills` | `uar/skills/llm_*.py` |
| GraphRAG | `graphrag_local`, `graphrag_global` | `uar/skills/graphrag_skills.py` |
| Blockchain | `cipher_ops`, `blockchain` | `uar/skills/cipher_ops.py` |
| Autonomi | `autonomi_storage` | `uar/skills/autonomi_storage.py` |
| UOR Ecosystem | `uor_address`, `uor_witness` | `uar/skills/uor_ecosystem_skills.py` |

---

## 5. Trust Spine

### 5.1 T1 — Replay Confidence
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Score replay | `uar/core/replay_confidence.py` | internal | — | ✅ |
| Per-run confidence | `uar/core/replay_confidence.py` | `GET /api/uar/runs/{id}/confidence` | **Missing** | 🔴 |
| Tier classification | `uar/core/replay_confidence.py` | API | — | ✅ |
| Warning generation | `uar/core/replay_confidence.py` | API | — | ✅ |

### 5.2 T2 — Runtime Health
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Component scoring | `uar/core/runtime_health.py` | internal | — | ✅ |
| Composite score | `uar/core/runtime_health.py` | `GET /api/uar/health/runtime` | **Missing** | 🔴 |
| Store health | `uar/core/runtime_health.py` | API | — | ✅ |
| Registry health | `uar/core/runtime_health.py` | API | — | ✅ |
| Snapshot query | `uar/core/runtime_health.py` | internal | — | ✅ |

### 5.3 T3 — Burn-In
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Smoke runner | `uar/testing/burnin/runner.py` | `POST /api/uar/burnin/run` | **Missing** | 🔴 |
| Soak runner | `uar/testing/burnin/runner.py` | internal | — | ✅ |
| Pressure runner | `uar/testing/burnin/runner.py` | internal | — | ✅ |
| Report persistence | `uar/api/routers/burn_in.py` | `GET /api/uar/burnin/latest` | **Missing** | 🔴 |
| BurnInProxy | `uar/api/routers/burn_in.py` | internal | — | ✅ |

### 5.4 T4 — Certification
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Composite scoring | `uar/core/certification.py` | internal | — | ✅ |
| Level derivation | `uar/core/certification.py` | `GET /api/uar/certification` | **Missing** | 🔴 |
| Evidence bundle | `uar/core/certification.py` | API | — | ✅ |
| Weighted inputs | `uar/core/certification.py` | API | — | ✅ |

### 5.5 T5 — Mission Control
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Snapshot aggregation | `uar/core/mission_control.py` | `GET /api/uar/mission-control` | **Missing** | 🔴 |
| Multi-signal combine | `uar/core/mission_control.py` | API | — | ✅ |
| Warning dedup | `uar/core/mission_control.py` | API | — | ✅ |

### 5.6 T6 — Replay Explorer
| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Timeline extraction | `uar/core/timeline.py` | internal | — | ✅ |
| Explorer bundle | `uar/api/routers/replay_explorer.py` | `GET /api/uar/runs/{id}/explorer` | **Missing** | 🔴 |
| Failure path | `uar/api/routers/replay_explorer.py` | API | — | ✅ |
| Event inspection | `uar/api/routers/replay_explorer.py` | API | — | ✅ |

---

## 6. API Layer

### 6.1 Routers (all mounted in `uar/api/routers/__init__.py`)

| Router | Endpoints | Purpose | Auth |
|--------|-----------|---------|------|
| `health.py` | `/api/health/*` | Liveness, readiness, circuit breakers, dashboard | Mixed |
| `runs.py` | `/api/uar/run`, `/api/uar/runs/*` | Execute runs, query history | Bearer |
| `streaming.py` | `/api/uar/stream`, `/api/uar/ws` | SSE/WebSocket events | Bearer |
| `recipes.py` | `/api/uar/recipes` | Recipe listing | Bearer |
| `docs.py` | `/api/uar/docs/*` | Document upload, library, presets | Bearer |
| `metrics.py` | `/api/uar/metrics` | Prometheus metrics | Optional |
| `uor.py` | `/api/uar/uor/*` | UOR addressing, objects | Bearer |
| `cache_sandbox.py` | `/api/uar/cache/*` | Cache introspection | Bearer |
| `replay_confidence.py` | `/api/uar/runs/{id}/confidence` | T1 replay scoring | Bearer |
| `burn_in.py` | `/api/uar/burnin/*` | T3 burn-in run/query | Bearer + admin |
| `runtime_health.py` | `/api/uar/health/runtime` | T2 health report | Bearer |
| `certification.py` | `/api/uar/certification` | T4 certification report | Bearer |
| `mission_control.py` | `/api/uar/mission-control` | T5 aggregate snapshot | Bearer |
| `replay_explorer.py` | `/api/uar/runs/{id}/explorer` | T6 run inspection | Bearer |

### 6.2 Middleware
| Capability | Module | Status |
|-----------|--------|--------|
| Auth (Bearer/JWT) | `uar/api/middleware.py` | ✅ |
| Rate limiting | `uar/api/middleware.py` | ✅ |
| Request logging | `uar/api/middleware.py` | ✅ |
| Error handling | `uar/api/middleware.py` | ✅ |
| CORS | `uar/boot.py` | ✅ |
| Tracing | `uar/api/tracing.py` | ✅ |

---

## 7. Mission Control

| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Snapshot model | `uar/core/mission_control.py` | `GET /api/uar/mission-control` | **Missing** | 🔴 |
| Runtime Health card | — | API | **Missing** | 🔴 |
| Replay Confidence card | — | API | **Missing** | 🔴 |
| Certification badge | — | API | **Missing** | 🔴 |
| Burn-In status | — | API | **Missing** | 🔴 |
| Active runs list | — | API | Partial (`runsHistory`) | 🟡 |
| Alerts / Warnings | — | API | **Missing** | 🔴 |

**Note:** The only health UI is `HealthDashboard.tsx`, which uses the **legacy**
`/api/health/dashboard` endpoint (skill availability + circuit breakers only).
It does not display Trust Spine signals.

---

## 8. Replay Explorer

| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Run summary | `uar/api/routers/replay_explorer.py` | `GET /api/uar/runs/{id}/explorer` | **Missing** | 🔴 |
| Event timeline | `uar/core/timeline.py` | API | `RecipeTimeline` (partial) | 🟡 |
| Failure path | `uar/api/routers/replay_explorer.py` | API | **Missing** | 🔴 |
| Confidence overlay | `uar/api/routers/replay_explorer.py` | API | **Missing** | 🔴 |
| Evidence inspector | — | API | **Missing** | 🔴 |
| Run comparison | — | — | **Missing** | 🔴 |

---

## 9. Topology

| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Topology service | — | — | — | ❌ Not started |
| Runtime graph | — | — | — | ❌ Not started |
| Execution graph | — | — | — | ❌ Not started |
| Visualization | — | — | — | ❌ Not started |

**Clarification needed:** Is topology for operator visibility (Mission Control)
or execution planning (Runtime Core)? See `docs/audit/TOPOLOGY_CLARIFICATION.md`.

---

## 10. Observability

| Capability | Module | API | UI | Status |
|-----------|--------|-----|-----|--------|
| Prometheus metrics | `uar/api/routers/metrics.py` | `/api/uar/metrics` | — | ✅ |
| Grafana dashboards | `deploy/grafana/` | — | — | ✅ |
| Alertmanager | `observability/alertmanager.yml` | — | — | ✅ |
| Loki logs | `observability/loki.yml` | — | — | ✅ |
| Circuit breaker states | `uar/api/routers/health.py` | `/api/health/circuit-breakers` | `HealthDashboard` | ✅ |

---

## Summary: What is Complete vs Missing

### Complete (Backend)
- Execution, Stores, Streaming, Skills, Registry, API middleware, Trust Spine scoring

### Complete (Frontend)
- Skill selector, recipe builder, event stream, file picker, old health dashboard

### Missing (Frontend — Priority Order)
1. **Mission Control Widget** (`GET /api/uar/mission-control`)
2. **Runtime Health Card** (`GET /api/uar/health/runtime`)
3. **Certification Badge** (`GET /api/uar/certification`)
4. **Burn-In Trigger + Status** (`POST/GET /api/uar/burnin/*`)
5. **Replay Confidence Card** (`GET /api/uar/runs/{id}/confidence`)
6. **Replay Explorer Panel** (`GET /api/uar/runs/{id}/explorer`)
7. **Active Runs Dashboard** (enhance existing `runsHistory`)

### Not Started
- Topology service, visualization, data service
