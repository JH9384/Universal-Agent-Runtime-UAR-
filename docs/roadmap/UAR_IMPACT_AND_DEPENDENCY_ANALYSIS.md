# UAR Impact and Dependency Analysis

> Updated 2026-06-05. Comprehensive 1st/2nd/3rd-order impact analysis with full precedent and dependency chains.

---

## Issue 1: Monolithic Architecture — No Internal Protocol Boundaries

### Impact Chain

| Order | Effect | Evidence |
|-------|--------|----------|
| **1st** | All components run in one Python process | `uar/api/state.py:198-204` — services instantiated at import time |
| **2nd** | Cannot scale executor independently; CPU-bound skills starve I/O; WebSocket handlers block on sync executor bridge | `uar/services/execution.py:519-521` — `_next_batch()` blocks a thread per execution |
| **3rd** | **Architectural lock-in**: Any horizontal scaling requires rewriting the entire event contract. The `distributed.py` aspirational comment (`"Can be extended to use remote workers via RPC"`) is never instantiated. Scaling past single-node is a **rewrite, not a refactor**. |

### Precedent Chain (upstream causes)

```
boot.py:420 — ctx = boot()
  → boot.py:410 — from uar.api.middleware import require_auth
    → server.py:23-49 — from uar.api.state import store, _auth_svc, _event_svc, _exec_svc
      → state.py:198-204 — _exec_svc = GoalExecutionService(event_service=_event_svc, store=store, ...)
        → services/execution.py:496 — executor = Executor()
          → core/executor.py:822 — iter_events() yields sync dicts directly
            → services/execution.py:519-521 — run_in_executor(None, _next_batch) [thread bridge]
```

**Precedent root cause:** `state.py` instantiates services at import time with hardcoded defaults instead of using a factory/container.

### Dependant Chain (downstream consumers)

```
_exec_svc.stream_goal() consumed by:
├── streaming.py:375 — WebSocket handler
├── streaming.py:543 — SSE handler
├── streaming.py:929 — Batch WebSocket handler
│
└── All 3 transport layers feed the SAME sync Executor via the SAME thread bridge.
    No alternative backend exists. The "distributed" executor (distributed.py:269)
    is just ThreadPoolExecutor with a comment.
```

**Dependant vulnerability:** Every transport layer shares one Executor. A CPU-bound skill blocks the thread that `_next_batch()` occupies, stalling ALL concurrent streams because they share the same thread pool. No isolation between clients.

---

## Issue 2: Production Code Imports from testing/

### Impact Chain

| Order | Effect | Evidence |
|-------|--------|----------|
| **1st** | `BurnInRunner` imported in production router | `uar/api/routers/burn_in.py:294` |
| **2nd** | Test utilities become production dependencies; Docker image bloat; testing/ cannot be excluded | `pyproject.toml:36-52` — dev deps include pytest, hypothesis, ruff |
| **3rd** | **CI/CD contamination**: Production artifact carries test code. A compromised test dependency (supply chain attack on pytest plugin) becomes a production vulnerability. The organizational boundary between engineering and operations erodes — production systems depend on development tooling, coupling operational stability to development velocity. |

### Precedent Chain

```
burn_in.py:291-294
  from uar.api.server import store
  from uar.core.registry import registry
  from uar.testing.burnin.runner import BurnInRunner  ← production imports testing

  runner = BurnInRunner(mode="direct", store=store, registry=registry)
```

**Precedent root cause:** `BurnInRunner` is the only burn-in orchestration implementation. No production-grade `BurnInService` was extracted.

### Dependant Chain

```
BurnInRunner consumed by:
├── burn_in.py:296-301 — /api/uar/burn-in/run endpoint (production API)
├── testing/burnin/runner.py — imports testing/burnin/scenarios.py
│   └── scenarios.py imports core/executor.py, core/registry.py, memory/base_store.py
│
└── Docker image (Dockerfile.prod) — COPY . . includes tests/
    └── CI optional-dependency-smoke job — tests importability of ALL code paths
```

**Dependant vulnerability:** `testing/` package becomes a production dependency. CI `optional-dependency-smoke` validates that ALL code paths import successfully, blurring the boundary.

---

## Issue 3: Global Mutable State (state.py side effects at import)

### Impact Chain

| Order | Effect | Evidence |
|-------|--------|----------|
| **1st** | Importing `state.py` creates DB connections + background threads | `uar/api/state.py:162-204` |
| **2nd** | Unit tests require env gymnastics; autouse fixture resets global rate limiter | `tests/conftest.py:40-47` |
| **3rd** | **Operational fragility under load**: SQLite writer thread is global. Under multi-worker Uvicorn (4 workers), each spawns its own writer thread writing to the same SQLite file without WAL coordination. The `_writer_exception` field is per-process — one worker's poisoned state does not propagate to others, causing **silent partial data loss**. |

### Precedent Chain

```
state.py:158-173 — Module-level store selection:
  if _UAR_STORE_BACKEND == "postgres": store = PostgresRunStore()
  elif _UAR_STORE_BACKEND == "sqlite": store = SqliteRunStore()
  else: store = JsonRunStore()

state.py:198-204 — Module-level service instantiation:
  _auth_svc = AuthService()
  _event_svc = EventService()
  _exec_svc = GoalExecutionService(event_service=_event_svc, store=store, ...)

state.py:44-45 — Module-level SSE connection state:
  _sse_connections: Dict[str, int] = {}
  _sse_connections_lock = asyncio.Lock()
```

**Precedent root cause:** No dependency injection container. Services created as module globals because no central registry manages lifecycles.

### Dependant Chain

```
state.py imported by 19 production modules:
├── api/routers/operator/*.py (13 files) — import store
├── api/routers/health.py — imports _uar_start_time
├── core/activity_log.py, core/credential_vault.py, core/data_source_registry.py,
│   core/maintenance.py, core/mission_control.py — core modules importing API layer
├── skills/dependency_map.py
│
└── tests/conftest.py:40-47 — autouse fixture:
      def reset_rate_limiter():
          from uar.api.middleware import reset_rate_limiter
          reset_rate_limiter()
      # Required because rate limiter is global mutable state

└── 32 test files patch uar.api.server names directly:
    └── test_trust_spine_fixes.py (18 references)
```

**Dependant vulnerability:** Multi-worker Uvicorn: 4 workers × SqliteRunStore writer thread = 4 threads writing to same SQLite file. `_writer_exception` is per-process, so one worker's poisoned state doesn't propagate — partial silent data loss.

---

## Issue 4: Dual 401 Error Codes ("unauthorized" vs "authentication_required")

### Impact Chain

| Order | Effect | Evidence |
|-------|--------|----------|
| **1st** | Test assertions must accept both strings | `tests/api/test_mission_control_auth.py:48-50` |
| **2nd** | Client SDKs implement fallback; API docs inconsistent; support tickets increase | `tests/api/test_trust_spine_fixes.py:2465-2467` |
| **3rd** | **API contract entropy**: Every new endpoint developer must choose which error code to use. Over time, the API accumulates inconsistent error vocabularies. Partner integrations break silently because they only handle one variant. When versioning becomes necessary, the migration path is harder. |

### Precedent Chain

```
middleware.py:665-714 — auth_middleware():
  if not credentials:
      raise HTTPException(status_code=401, detail={"error": "unauthorized", ...})
  └── BUT: this is the GLOBAL middleware path

mission_control.py:66-72 — Endpoint-level guard:
  raise HTTPException(status_code=401, detail={"error": "authentication_required", ...})
  └── Same pattern in burn_in.py, runs.py, topology.py, rbac.py, certification.py,
      replay_confidence.py, replay_explorer.py, runtime_health.py (28 total occurrences)
```

**Precedent root cause:** Two separate auth enforcement layers (global middleware + per-endpoint guards) written by different authors without a shared error code constant.

### Dependant Chain

```
"authentication_required" raised by:
├── mission_control.py (17 occurrences)
├── burn_in.py (2), runs.py (2), topology.py (2), rbac.py (1), certification.py (1),
│   replay_confidence.py (1), replay_explorer.py (1), runtime_health.py (1)

"unauthorized" raised by:
├── middleware.py — global auth_middleware
└── middleware.py:975-1004 — require_auth function

Tests handling BOTH:
├── test_mission_control_auth.py:48-50 — assert error in ("unauthorized", "authentication_required")
└── test_trust_spine_fixes.py:2465-2469 — comment explains the mismatch
```

**Dependant vulnerability:** Every new endpoint author must choose which string to return. Client SDKs must implement fallback logic. The API contract becomes inconsistent over time.

---

## Issue 5: _parse_ports No-Op (Silent Data Loss)

### Impact Chain

| Order | Effect | Evidence |
|-------|--------|----------|
| **1st** | Every Verilog module reports `total_ports: 0` | `uar/skills/verilog_parse.py:44-48` |
| **2nd** | Downstream tools receive incomplete metadata; users cannot trust skill output; failure is invisible | `uar/skills/verilog_parse.py:27-40` — `_parse_ports(ports_str)` returns `[]` silently |
| **3rd** | **Compounding silent failures**: A workflow depending on port count (e.g., "connect all output ports to testbench") silently does nothing. The user loses trust without knowing why. Over time, this erodes the Trust Spine (T1-T6) that UAR invested heavily in building. A system certifying replay confidence but silently dropping data is self-undermining. |

### Precedent Chain

```
verilog_parse.py:44-48
  def _parse_ports(ports_str: str) -> List[Dict[str, str]]:
      ports: List[Dict[str, str]] = []
      # Handle ANSI-style port declarations within module body
      return ports   ← COMPLETE NO-OP

verilog_parse.py:27-30
  name = match.group(1)
  ports_str = match.group(2)
  body = match.group(3)
  ports = _parse_ports(ports_str)  ← always receives []
```

**Precedent root cause:** `_parse_ports` was stubbed during initial development and never implemented. No test verified port count accuracy.

### Dependant Chain

```
verilog_parse skill consumed by:
├── skills/__init__.py:52 — import uar.skills.verilog_parse (auto-registered at startup)
├── uar/core/registry.py — skill registered under name "verilog_parse"
│
└── Any goal/execution_order referencing "verilog_parse":
    ├── Frontend UARPanel — user selects skill
    ├── API /api/uar/run — skill executed via Executor
    └── Result payload includes:
        {"modules": [...], "total_ports": 0, "signals": [...], ...}
```

**Dependant vulnerability:** Any workflow depending on port metadata receives silently incorrect data. The Trust Spine certifies consistency of wrong data — worse than inconsistency of right data.

---

## Issue 6: except Exception: pass in Operational Paths

### Impact Chain

| Order | Effect | Evidence |
|-------|--------|----------|
| **1st** | Audit logging and webhook alerts fail silently | `uar/api/routers/operator/common.py:88-106` |
| **2nd** | Security incidents not alerted; compliance auditors find missing logs; post-incident investigation fails | `docs/ENTERPRISE_REVIEW_AND_PLAN.md:61` — "No audit log retention policy" |
| **3rd** | **Operational learned helplessness**: When every failure path swallows exceptions, operators cannot distinguish "system healthy" from "system failing gracefully." The SRE team would be unable to build reliable runbooks. The culture shifts from "fix the root cause" to "restart and hope" — the only observable symptom is often "things seem slower" or "outputs look weird." This is the path to outages that take days to diagnose because no telemetry exists. |

### Precedent Chain

```
"Best-effort" pattern used in:
├── common.py:88-106 (FIXED in this session)
│   ├── audit_admin_action audit log — except Exception: pass
│   └── audit_admin_action webhook alert — except Exception: pass
├── common.py:156-157 — Incident metadata scan: except Exception: logger.warning(...)
├── common.py:170-171 — Incident persistence: except Exception: logger.warning(...)
├── core/contracts.py — overflow file cleanup in __del__: except Exception: pass
└── core/self_update.py:119-120 — _version_lt fallback: except Exception: pass
```

**Precedent root cause:** Docstring states "Non-blocking: exceptions are swallowed so the main operation is never impeded." Implementation was too aggressive — didn't even log.

### Dependant Chain

```
audit_admin_action failures silently dropped:
├── No audit trail for admin actions
├── No webhook alerts for security events (DELETE, failure, denied)
├── Compliance auditors find missing logs
└── Post-incident investigation cannot reconstruct what happened

incident/snapshot/inbox persistence failures:
├── _persist_incident() fails → incident disappears
├── _persist_snapshot() fails → snapshot not saved
└── _persist_inbox_item() fails → inbox item lost
    → Mission Control shows stale or missing data
```

**Dependant vulnerability:** When failures are invisible, operators cannot build reliable runbooks. The SLO-C1 "Post-Recovery Fidelity = 100%" becomes unverifiable if the recovery path itself fails silently.

---

## Issue 7: Self-Reported SLA with No External Validation

### Impact Chain

| Order | Effect | Evidence |
|-------|--------|----------|
| **1st** | Metrics are in-memory; lost on restart | `docs/SLA.md:91` — "No external metrics persistence" |
| **2nd** | Availability claims unverifiable; customer SLAs unenforceable; refunds have no data basis | `docs/SLA.md:92-93` — "No synthetic probing; no alert wiring" |
| **3rd** | **Organizational blindness**: When the only measurement is self-reported, the engineering team optimizes for metrics that look good rather than metrics that are real. This creates a "works on my machine" culture at scale. Investment goes to features improving internal metrics rather than user-observable outcomes. The competitive gap with external monitoring (Datadog, New Relic) widens until a major customer churn event forces a reactive, expensive overhaul. |

### Precedent Chain

```
api/metrics.py:55-617 — Custom MetricsCollector class
  ├── In-memory only
  ├── Optional Redis persistence (lazy, opt-in via REDIS_URL)
  └── _get_redis() returns None if Redis unavailable

api/metrics.py:151-200 — Prometheus format generation:
  def get_prometheus_format() -> str:
      # Generates exposition format from in-memory state
```

**Precedent root cause:** `MetricsCollector` was built as lightweight internal tool before external monitoring was considered. Redis persistence was an afterthought.

### Dependant Chain

```
Metrics consumed by:
├── api/routers/metrics.py — GET /api/metrics (Prometheus format)
│   └── Optional METRICS_API_KEY protection
├── api/middleware.py — metrics_middleware records every endpoint
├── core/executor.py — record_skill() records per-skill latency
├── boot.py:473 — register_metrics_middleware(app)
│
└── SLA.md claims:
    ├── Core API Availability: 99.9%
    ├── Health Probes: 99.95%
    ├── POST /api/uar/run p99: < 5,000ms
    └── 5xx Error Rate: < 0.1%

    BUT SLA.md §3.2 acknowledges:
        ├── "No external metrics persistence" — metrics lost on restart
        ├── "No synthetic probing" — availability is self-reported
        └── "No alert wiring" — cannot enforce MTTD/MTTR
```

**Dependant vulnerability:** The SLA is a specification, not an enforced contract. No customer can verify the 99.9% availability claim. No PagerDuty alert fires when p99 exceeds 5s. The engineering team optimizes for internal metrics rather than user-observable outcomes.

---

## Issue 8: No Encryption at Rest

### Impact Chain

| Order | Effect | Evidence |
|-------|--------|----------|
| **1st** | SQLite/JSONL files stored in plaintext | `docs/ENTERPRISE_REVIEW_AND_PLAN.md:46` — "ALLOWED_ROOT defaults to Path.cwd()" |
| **2nd** | Data breach exposes all run history; GDPR Art. 32 violation; SOC 2 Type II audit failure | `docs/ENTERPRISE_REVIEW_AND_PLAN.md:62` — "No PII detection" |
| **3rd** | **Existential business risk**: Under GDPR, a breach of unencrypted personal data must be reported to regulators within 72 hours. If UAR is used in healthcare or financial context (high-risk under EU AI Act Art. 6), the liability is not just fines — it's criminal liability for senior management. The `ENTERPRISE_REVIEW_AND_PLAN.md` rates security 9/10, but the absence of encryption at rest makes this score **unwarranted** for any regulated deployment. |

### Precedent Chain

```
memory/json_store.py:19-21 — JsonRunStore
  "Append-only JSONL storage... simple, portable, easy to inspect"

memory/sqlite_store.py:27-33 — SqliteRunStore
  Uses sqlite3.connect(path) with NO encryption PRAGMA

memory/postgres_store.py:98-101 — PostgresRunStore
  Uses psycopg2 with standard connection (no SSL enforcement in code)

services/execution.py:165-174 — Temp file for event buffering:
  tmp_path = tempfile.NamedTemporaryFile(mode="wb" or "w", delete=False)
  # No encryption on temp file
```

**Precedent root cause:** Storage backends were built for developer convenience ("easy to inspect") rather than production security.

### Dependant Chain

```
All data written plaintext:
├── JsonRunStore — JSONL files in runs/ directory
├── SqliteRunStore — uar_runs.db SQLite file
├── PostgresRunStore — PostgreSQL table (relies on DB admin for encryption)
├── services/execution.py temp files — .jsonl or .jsonl.gz in /tmp
│
└── Consumers of plaintext data:
    ├── /api/uar/run — persists run records
    ├── /api/uar/stream — persists events to temp file then store
    ├── Mission Control — reads historical runs
    ├── Replay Explorer — replays events from store
    ├── Burn-In Framework — stores certification reports
    └── Operator dashboards — display all historical data
```

**Dependant vulnerability:** Under GDPR Article 32, personal data must be protected with "appropriate technical measures" including encryption. A breach of the `runs/` directory exposes every execution record, user prompt, and skill output in plaintext. The security 9/10 score is **unwarranted** for any regulated deployment.

---

## Cross-Issue Compound Risk Matrix

| Combination | Compound Effect | Tasks That Address It |
|-------------|-----------------|----------------------|
| Global state + No encryption + No immutable audit | Compromised process reads all history, modifies state, erases tracks | T1 + T2 + T3 |
| Monolithic architecture + Self-reported SLA + No probing | System down for real users while metrics show green | T5 + T7 + T8 |
| Silent failures + No-op parsers + Testing imports production | Bugs accumulate invisibly; test suite passes; real workflows silently fail | T1 + T3 + T4 + BUG fixes |
| Dual error codes + No API versioning + No contract tests | API surface becomes inconsistent; breaking changes accidental | T9 |

---

## Priority Reordering by Compound Risk

| Priority | Issue | Rationale |
|----------|-------|-----------|
| **P0** | Immutable audit logs + Encryption at rest | **Existential**: GDPR breach, criminal liability, total data exposure |
| **P0** | Remove testing/ imports from production | **Supply chain**: Expands attack surface; test code in production is a control failure |
| **P1** | Normalize error codes + API versioning | **Customer trust**: Silent client breakage is churn you cannot explain |
| **P1** | External SLA validation (synthetic probes) | **Operational reality**: Self-reported metrics are fiction under load |
| **P2** | Extract internal protocol boundaries | **Scaling**: Cannot horizontal-scale without this; but it's a rewrite, so plan carefully |
| **P2** | Replace all bare `except: pass` with logged warnings | **Observability**: The current state is operational blindness |

---

## Single Root Cause

Every gap traces back to one architectural decision:

> **Global mutable state in `state.py` instantiated at import time**

This decision:
- Prevents true modularity (G1)
- Makes observability self-referential (G2)
- Prevents production-grade security (G3/G9)
- Undermines trust evidence (G4)
- Fragments metrics across workers (G10)
- Violates store independence (G6)
- Makes guarantees untestable under load (G7)
- Renders SLA claims unverifiable (G8)

**Fixing `state.py` — replacing module-level globals with dependency injection and factory patterns — would not solve everything, but it would unblock solutions to G1, G6, G7, and G10.** Without it, the other improvements are patches on a fundamentally coupled design.
