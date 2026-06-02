# UAR Architecture

**Version:** 1.2.0 (see `VERSION` file)  
**Last Updated:** 2026-06-01

---

## 1. System Overview

Universal Agent Runtime (UAR) is a modular, event-driven execution platform that operates as both an **agent runtime** (goal-oriented, event-streamed, observable workflows) and a **browser-accessible scientific computing sandbox** (quantum circuits, molecular dynamics, RISC-V emulation, Verilog simulation, astrophysics computations).

It consists of a Python backend (FastAPI + custom executor with 127 registered skills) and an optional React frontend, communicating over HTTP and WebSocket. Skills span AI/LLM integration, document processing, hardware emulation, embedded systems, and pure mathematics — all exposed through a unified JSON goal API.

## 2. High-Level Architecture

```mermaid
graph TD
    subgraph Client["Client Layer"]
        C1[React Web<br/>Vite]
        C2[curl / CLI]
        C3[External Services<br/>UOR, Hologram]
    end

    subgraph API["API Layer (FastAPI)"]
        A1[/api/uar/run<br/>/api/uar/stream/]
        A2[/api/uar/stream/ws]
        A3[/api/health/*<br/>/api/metrics<br/>/api/uar/recipes]
        MW[Middleware Pipeline<br/>CORS → Rate Limit → Auth → Logging]
    end

    subgraph Core["Core Runtime Layer"]
        P[Planner<br/>strategy]
        E[Executor<br/>event loop]
        R[Skill Registry<br/>dynamic lookup]
        SE[Skill Execution Engine<br/>Sequential → Parallel → Retry → CB → Cache → Guardrails]
    end

    subgraph Persist["Persistence Layer"]
        S1[JSONL / SQLite / Postgres<br/>run records]
        S2[Audit Logger<br/>compliance]
        S3[Cache<br/>Redis / in-mem]
    end

    subgraph Trust["Trust Spine"]
        T1[Replay Confidence]
        T2[Runtime Health]
        T3[Burn-In Framework]
        T4[Certification Engine]
        T5[Mission Control]
    end

    subgraph Ops["Operational Intelligence"]
        O1[Analytics]
        O2[Search]
        O3[Knowledge Graph]
        O4[Insight Generation]
    end

    C1 -->|HTTP / WebSocket| A1
    C2 -->|HTTP| A1
    C3 -->|HTTP| A1
    A1 --> MW
    A2 --> MW
    A3 --> MW
    MW --> P
    P --> E
    E --> R
    E --> SE
    SE --> S1
    SE --> S2
    SE --> S3
    S1 --> T1
    S1 --> T2
    T1 --> T3
    T2 --> T3
    T3 --> T4
    T4 --> T5
    T5 --> O1
    O1 --> O2
    O2 --> O3
    O3 --> O4
```

### 2.1 Trust Spine Evidence Flow

```mermaid
graph LR
    subgraph Evidence["Evidence Collection"]
        R1[Replay<br/>Confidence]
        R2[Runtime<br/>Health]
        R3[Burn-In<br/>Framework]
    end

    subgraph Trust["Trust Formation"]
        T1[Certification<br/>Engine]
        T2[Trust<br/>Computation]
    end

    subgraph Operations["Operator Facing"]
        O1[Mission<br/>Control]
        O2[Replay<br/>Explorer]
    end

    R1 --> T1
    R2 --> T1
    R3 --> T1
    T1 --> T2
    T2 --> O1
    T2 --> O2
```

### 2.2 Operational Intelligence Platform Layers

```mermaid
graph TD
    subgraph L1["Foundation"]
        A1[Runtime<br/>Execution, skills, streaming]
        A2[Observability<br/>Health, metrics, Prometheus/Grafana]
    end

    subgraph L2["Learning & Evidence"]
        B1[Learning<br/>Pattern recognition, feedback, quality]
        B2[Evidence<br/>Replay confidence, UOR provenance]
        B3[Trust<br/>Trust computation, trust-aware ranking]
        B4[Validation<br/>Burn-in, certification, conformance]
    end

    subgraph L3["Operations"]
        C1[Operations<br/>Mission control, replay explorer]
        C2[Workflow<br/>Briefing, workbench, explorer]
    end

    subgraph L4["Intelligence"]
        D1[Search<br/>Operational search, investigation replay]
        D2[Knowledge Graph<br/>Topology, graph v2, time machine]
        D3[Analytics<br/>Cross-run analytics, trust overlay]
        D4[Insight Generation<br/>Patterns, evolution, clusters, intelligence]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
```

## 3. Component Breakdown

### 3.1 API Layer (`uar/api/`)

| Component | File | Purpose |
|-----------|------|---------|
| **Server** | `server.py` | FastAPI app, endpoint definitions, lifespan management |
| **Middleware** | `middleware.py` | Rate limiting, auth, request logging, security headers |
| **Metrics** | `metrics.py` | Prometheus-compatible histograms, p50/p99 tracking |
| **Security** | `security.py` | CSP, CORS, input validation helpers |
| **Routers** | `routers/*.py` | UOR object endpoints, recipe CRUD, health probes |

### 3.2 Core Runtime (`uar/core/`)

| Component | File | Purpose |
|-----------|------|---------|
| **Planner** | `planner.py` | Converts GoalSpec + execution_order into StrategySpec |
| **Executor** | `executor.py` | Event-driven execution engine with retry, caching, guardrails |
| **Registry** | `registry.py` | Thread-safe skill registration and `@register_skill` decorator |
| **Contracts** | `contracts.py` | Dataclasses: PipelineContext, RunRecord, StrategySpec, GoalSpec |
| **Safe Eval** | `safe_eval.py` | Restricted AST expression evaluator for STEM skills |
| **Validation** | `validation.py` | Path traversal prevention, timeout validation |
| **Audit** | `audit.py` | JSONL audit logger for compliance |

### 3.3 Skills (`uar/skills/`)

| Category | Skills |
|----------|--------|
| **Document** | `doc_ingest`, `section_sum`, `sum_review` |
| **AI/LLM** | `ollama_generate` |
| **Knowledge Graph** | `graphrag_init`, `graphrag_index`, `graphrag_query` |
| **UOR Ecosystem** | `uor_foundation_verify`, `hologram_query`, `moltbook_*` |
| **STEM** | `scipy_opt`, `diff_eq_solve`, `qiskit_circuit`, `rdkit_*`, `relativity` |
| **ML/Data** | `optuna_tune`, `chromadb_store` |
| **CV** | `opencv_process`, `yolo_detect` |
| **Storage** | `autonomi_*` (experimental) |

### 3.4 Persistence (`uar/memory/`)

| Component | File | Purpose |
|-----------|------|---------|
| **JSONL Store** | `json_store.py` | Append-only run records with file locking |
| **Cache** | `cache.py` | Skill result caching (in-mem / Redis) |

## 4. Request Flow

### 4.1 HTTP Request (`POST /api/uar/run`)

```
Client Request
    │
    ▼
┌─────────────────┐
│  FastAPI Router │  ← Pydantic validation (RunRequest)
└────────┬────────┘
         │
    ┌────┴────┐
    ▼         ▼
┌────────┐ ┌────────┐
│ Rate   │ │ Auth   │  ← Per-skill rate limits, API key tiers
│ Limit  │ │        │
└───┬────┘ └────────┘
    │
    ▼
┌─────────────────┐
│ Request Logging │  ← Correlation ID, duration metrics, audit trail
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  _build_goal()  │  ← execution_order → ordered_skills + recipe_markers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ SimplePlanner   │  ← GoalSpec → StrategySpec
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│   Executor.run  │  ← Event loop: skill_start → skill_complete/failed
│                 │     Retry logic, circuit breaker, cache lookup
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  JSONL Store    │  ← Persist RunRecord
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  JSON Response    │  ← RunRecord serialized
└─────────────────┘
```

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant R as FastAPI Router
    participant M as Middleware
    participant P as SimplePlanner
    participant E as Executor
    participant S as JSONL Store

    C->>R: POST /api/uar/run (RunRequest)
    R->>M: Pydantic validation
    M->>M: Rate limit check
    M->>M: Auth + request logging
    M->>P: _build_goal() (execution_order)
    P->>P: Plan → StrategySpec
    P->>E: iter_events(strategy, goal)
    loop For each skill
        E->>E: Cache lookup
        alt Cache miss
            E->>E: Skill execution
            E->>E: Retry / circuit breaker
        end
        E-->>R: event (skill_start / skill_complete / recipe_start / recipe_end)
    end
    E->>S: Persist RunRecord
    R-->>C: RunResponse
```

### 4.2 WebSocket Stream (`/api/uar/stream/ws`)

```
WebSocket Connect
    │
    ▼
┌─────────────────┐
│  Connection Cap │  ← Max 1000 concurrent WS connections
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Rate Limit     │  ← Per-user/skill limits
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Auth (Bearer)  │  ← Token from header or query param
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Executor.stream│  ← Async generator yields events
│                 │     start → recipe_start → skill_start → skill_complete → recipe_end → metrics → complete
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  Binary Viz     │  ← Optional base64 visualization for skill_complete
└─────────────────┘
```

## 5. Data Model

### 5.1 Core Types

```python
# GoalSpec — what the user wants
class GoalSpec:
    objective: str          # Natural language goal
    metadata: dict          # input_path, auto_sum_review, etc.
    execution_order: list   # Unified skill + recipe order

# StrategySpec — how to execute
class StrategySpec:
    ordered_skills: list[str]      # Flattened skill names
    recipe_markers: list[dict]     # Recipe boundaries for nesting
    parallel_groups: list[list]    # Skills that can run in parallel

# RunRecord — what happened
@dataclass
class RunRecord:
    run_id: UUID
    goal_id: UUID
    skills: list[str]
    outputs: list[dict]
    status: str             # "completed" | "partial" | "failed"
    errors: list[str]
    events: list[dict]
    final_context: dict
    user_id: str | None
```

### 5.2 Event Schema

```python
{
    "type": "skill_start" | "skill_complete" | "skill_failed" |
            "skill_retry" | "recipe_start" | "recipe_end" |
            "metrics" | "start" | "complete",
    "skill": str,           # Skill name (if applicable)
    "recipe": str,          # Recipe name (if applicable)
    "timestamp": float,     # Unix epoch
    "error": str | None,
    "payload": dict,        # Skill-specific output
    "request_id": str,
    "correlation_id": str,
}
```

## 6. Security Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Perimeter                         │
│  CORS origins whitelist → CSP headers → HSTS       │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────┐
│                Transport                             │
│  TLS termination → Request body size limit (50MB)    │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────┐
│                Authentication                        │
│  API Key (Bearer) → Tier-based rate limits          │
│  Metrics API Key (optional, production)             │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────┐
│              Authorization                           │
│  Resource ownership checks → Canonical recipe locks  │
└────────────────────┬────────────────────────────────┘
                     │
┌────────────────────┼────────────────────────────────┐
│              Application Security                    │
│  Path traversal validation → File size/count caps   │
│  safe_eval (AST) → SSRF prevention                  │
│  Input guardrails → Output guardrails               │
└─────────────────────────────────────────────────────┘
```

## 7. Deployment Architecture

### 7.1 Local Development

```
┌─────────────┐     ┌─────────────┐
│  React Dev  │────▶│  Vite HMR   │  http://localhost:5173
│   Server    │     │   (5173)    │
└─────────────┘     └─────────────┘
                           │
┌─────────────┐     ┌──────┴──────┐
│   Uvicorn   │────▶│  FastAPI    │  http://localhost:8000
│   (8000)    │     │   (API)     │
└─────────────┘     └──────┬──────┘
                           │
                    ┌──────┴──────┐
                    │  JSONL Store │  ./runs/
                    │  (optional)  │
                    └─────────────┘
```

### 7.2 Production (Docker Compose)

```mermaid
graph TD
    Client[Client]
    Nginx[Nginx<br/>TLS termination, static files]
    UAR1[UAR API<br/>Worker 1 :8000]
    UAR2[UAR API<br/>Worker 2 :8000]
    UAR3[UAR API<br/>Worker 3 :8000]
    Redis[Redis<br/>Shared rate limits + skill cache]
    Store[JSONL / SQLite / Postgres<br/>Run persistence<br/>mounted volume]

    Client -->|HTTPS| Nginx
    Nginx -->|Proxy| UAR1
    Nginx -->|Proxy| UAR2
    Nginx -->|Proxy| UAR3
    UAR1 --> Redis
    UAR2 --> Redis
    UAR3 --> Redis
    UAR1 --> Store
    UAR2 --> Store
    UAR3 --> Store
```

## 8. Monitoring & Observability

```
┌─────────────────────────────────────────────────────────────┐
│                        Metrics Pipeline                        │
│                                                                │
│  Request ──▶ MetricsCollector ──▶ /api/metrics (Prometheus) │
│              (histograms, p50/p99)                             │
│                                                                │
│  Skill  ────▶ record_skill() ─────▶ uar_skill_duration_seconds │
│  Execution                                                    │
│                                                                │
│  Health ────▶ /api/health/live  ──▶ K8s liveness probe         │
│  Checks    ──▶ /api/health/ready ──▶ K8s readiness probe       │
│                                                                │
│  Audit  ────▶ JSONL audit.log ───▶ Compliance / forensics     │
└─────────────────────────────────────────────────────────────┘
```

## 9. Key Design Decisions

| Decision | Rationale |
|----------|-----------|
| **JSONL over SQL** | Append-only, file-locked, no schema migrations for v1 |
| **In-memory rate limiter default** | Zero-dependency startup; Redis for production multi-worker |
| **Event streaming over polling** | Real-time UX, backpressure via client ACK |
| **Skill registry at module load** | Decorator-based registration, no central registry file |
| **Recipe expansion at request time** | Execution_order allows mixing skills + recipes dynamically |
| **AST-based safe_eval** | Prevents sandbox escape vs `eval()` in STEM skills |

## 10. Extension Points

| Extension | How |
|-----------|-----|
| **New Skill** | `@register_skill("name")` decorator in `uar/skills/` |
| **New Recipe** | Add to `DEFAULT_RECIPES` in `uar/core/recipes.py` |
| **Custom Middleware** | Add to middleware pipeline in `uar/api/middleware.py` |
| **New Store Backend** | Implement `BaseStore` interface in `uar/memory/` |
| **Custom Planner** | Subclass `BasePlanner`, inject in `server.py` |

---

*See also:*
- [System Guide](../SYSTEM.md) — Internal development guide
- [Onboarding Guide](../ONBOARDING.md) — Zero-to-running for new users
- [SLA](SLA.md) — Service level objectives and monitoring gaps
- [Boot & Shutdown](BOOT_AND_SHUTDOWN.md) — Detailed startup/shutdown sequences
