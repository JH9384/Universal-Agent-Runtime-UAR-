# UAR Enterprise Review & Improvement Plan

**Version:** 1.0.0  
**Date:** 2026-05-22  
**Scope:** Production readiness, security posture, scalability, operational maturity

---

## 1. Executive Summary

UAR is a well-architected modular agent runtime with solid foundations in skill-based execution, event streaming, and security-minded design. The codebase demonstrates mature patterns: thread-safe rate limiting, path traversal protection, structured logging with correlation IDs, and comprehensive test coverage (490+ backend tests, 28 frontend tests).

**Overall Maturity Rating:** Beta → Production-Ready (with targeted improvements)

| Dimension | Score | Notes |
|-----------|-------|-------|
| Security | 7/10 | Good env-based secrets, path validation; eval() risks remain |
| Scalability | 5/10 | Single-process rate limiting; no horizontal scaling story |
| Observability | 6/10 | Custom metrics collector; no distributed tracing |
| Operations | 7/10 | Docker + health checks + entrypoint validation |
| API Stability | 7/10 | Pydantic models, versioned specs; missing OpenAPI validation |
| Test Quality | 8/10 | High coverage, alignment tests, conformance invariants |
| Documentation | 6/10 | Good README; missing runbooks and API guides |

---

## 2. Current State Assessment

### 2.1 Strengths

- **Skill registry pattern** enables clean plugin architecture with optional dependency handling.
- **Security middleware** includes rate limiting (in-memory + Redis), API key auth, request body size limits, path traversal validation, and structured audit logging.
- **Resource safety** in `doc_ingest`: generator-based streaming, file count/size caps, individual file error isolation.
- **Configuration management** in `config.py` distinguishes dev/prod, validates secrets, checks Docker permissions.
- **CI/CD matrix** tests multiple install variants (base, advanced, doc-processing, agent-orchestration).
- **Regression testing** is now formalized with Makefile targets and alignment tests.

### 2.2 Weaknesses

- **Rate limiter state** is process-local; breaks under multi-worker Uvicorn or container replication.
- **`eval()` in STEM skills** (`scipy_opt`, `diff_eq_solve`) is a sandbox escape risk for multi-tenant deployments.
- **`parse_request_body` middleware** consumes the ASGI request body stream, creating a subtle coupling with downstream endpoints.
- **Metrics** are custom-built and in-memory; no Prometheus scraping endpoint, no histograms, no p99 latencies.
- **No distributed tracing** (OpenTelemetry/Jaeger); debugging cross-service issues is difficult.
- **Secrets rotation** requires process restart; no hot-reload or secret provider integration (AWS Secrets Manager, Vault).
- **`ALLOWED_ROOT` defaults to `Path.cwd()`** if `PROJECT_ROOT` is unset — dangerous in production.

### 2.3 Opportunities

- Replace custom metrics with `prometheus-fastapi-instrumentator` for standard observability.
- Add OpenTelemetry tracing for skill execution spans.
- Implement a `@requires_package` decorator to DRY optional dependency checks across 10+ skill files.
- Add a `/health` readiness probe that checks Redis/SQLite dependency health, not just process liveness.
- Create a Helm chart for Kubernetes deployment with HPA and ingress.

### 2.4 Threats

- **Data exfiltration via eval()**: A malicious payload with a carefully crafted expression could access `__builtins__` or object internals.
- **DoS via memory exhaustion**: `_yield_documents` has caps, but `run/stream` endpoints with large `execution_order` arrays could cause unbounded memory growth.
- **Secret leakage in logs**: `request_logging_middleware` logs full URLs; query parameters containing tokens could be exposed.
- **Compliance gaps**: No audit log retention policy, no PII detection, no data retention TTL on `runs_dir`.

---

## 3. Gap Analysis by Dimension

### 3.1 Security & Compliance

| Gap | Risk | Current | Target |
|-----|------|---------|--------|
| `eval()` in skill expressions | **Critical** — sandbox escape | `eval(expr, {"np": np})` | Replace with `asteval` or custom parser |
| `ALLOWED_ROOT` defaults to CWD | **High** — path traversal in prod | `Path.cwd()` if env unset | Require explicit `PROJECT_ROOT` in production |
| No secret rotation | **Medium** — key compromise persistence | Module-level `API_KEYS` dict | Hot-reload via env or secret provider |
| No PII redaction in logs | **Medium** — GDPR/SOC2 risk | Full URL logging in middleware | Query param redaction, mask tokens |
| No audit log retention | **Medium** — compliance gap | JSON stdout logs | Structured log shipping + retention policy |
| WebSocket auth replay | **Low** — token replay risk | Static bearer tokens | Short-lived JWTs or mTLS |

### 3.2 Scalability & Performance

| Gap | Risk | Current | Target |
|-----|------|---------|--------|
| In-memory rate limiting | **High** — breaks multi-worker | `defaultdict(deque)` per process | Redis-backed by default in prod |
| No connection pooling for DB | **Medium** — SQLite serialized | `JsonRunStore` with file I/O | Connection pool + WAL mode |
| Single-threaded executor | **Medium** — CPU-bound skills block | `ThreadPoolExecutor(max_workers=16)` | Process pool for CPU skills, async for I/O |
| No caching layer | **Medium** — repeated work | Module-level recipe expansion cache | Redis/Memcached for skill results |
| WebSocket backpressure | **Low** — slow clients stall | Fixed `BACKPRESSURE_DELAY` | Dynamic backpressure with client ACK |

### 3.3 Observability & Reliability

| Gap | Risk | Current | Target |
|-----|------|---------|--------|
| Custom metrics, no scraping | **High** — ops blind spot | `MetricsCollector` in-memory | Prometheus `/metrics` endpoint |
| No distributed tracing | **Medium** — debugging pain | Correlation IDs only | OpenTelemetry spans + Jaeger |
| No health check depth | **Medium** — false positives | `curl /api/health` | Deep checks: DB, Redis, disk |
| No alerting thresholds | **Medium** — reactive ops | Manual log inspection | SLO-based alerts (error rate, latency) |
| No structured error codes | **Low** — client confusion | Human-readable messages | Machine-readable error codes |

### 3.4 Operational Maturity

| Gap | Risk | Current | Target |
|-----|------|---------|--------|
| No graceful shutdown | **Medium** — in-flight request loss | `uvicorn` default signal handling | Drain connections, finish active runs |
| No database migrations | **Medium** — schema drift | SQLite schema inline | Alembic migrations for UOR store |
| No backup strategy | **Medium** — data loss | JSONL files in `runs_dir` | Automated backup + point-in-time recovery |
| Dockerfile copies all files | **Low** — image bloat | `COPY . .` | Multi-stage build, exclude tests/docs |
| No resource quotas in k8s | **Low** — noisy neighbor | None | CPU/memory limits in Helm chart |

### 3.5 API Contract & Stability

| Gap | Risk | Current | Target |
|-----|------|---------|--------|
| No OpenAPI schema validation | **Medium** — drift risk | FastAPI auto-generated | `schemathesis` or `dredd` contract tests |
| Request body stream consumed | **Medium** — endpoint fragility | `await request.body()` in middleware | Custom `CachedRequest` or dependency-based parsing |
| No API versioning | **Low** — breaking changes | `/api/` prefix only | `/api/v1/`, `/api/v2/` with deprecation headers |
| Missing pagination on lists | **Low** — unbounded responses | Full list returns | Cursor-based pagination |

### 3.6 Testing & Quality

| Gap | Risk | Current | Target |
|-----|------|---------|--------|
| No performance/regression benchmarks | **Medium** — latency regression | `benchmark_skills.py` (non-blocking) | Automated performance gates in CI |
| No contract testing | **Medium** — frontend/backend drift | `test_feature_alignment.py` | Pact or OpenAPI contract validation |
| No chaos/fault injection | **Low** — resilience unknown | None | `chaos-monkey` for skill timeouts, DB failure |
| No accessibility testing | **Low** — a11y gaps | None | `axe-core` in frontend CI |

---

## 4. Prioritized Improvement Roadmap

### Phase 1: Security Hardening (Weeks 1–2)
**Goal:** Remove critical and high-risk security gaps before production deployment.

1. **Replace `eval()` in STEM skills**
   - Files: `uar/skills/stem_extended.py`
   - Action: Implement `safe_eval()` using `asteval` (0.9+) or a restricted AST parser. Block `__builtins__`, attribute access, and imports.
   - Acceptance: Fuzz test with 100 malicious expressions — all blocked.

2. **Enforce explicit `PROJECT_ROOT` in production**
   - Files: `uar/skills/doc_ingest.py`, `uar/config.py`
   - Action: In `validate_environment()`, fail if `is_production and not os.getenv("PROJECT_ROOT")`.
   - Acceptance: Docker entrypoint exits with clear error if unset.

3. **Redact sensitive query params in logs**
   - Files: `uar/api/middleware.py`
   - Action: In `request_logging_middleware`, parse URL and mask known sensitive keys (`token`, `key`, `secret`, `password`).
   - Acceptance: Log contains `?token=***&foo=bar`.

4. **Add security headers middleware**
   - Files: `uar/api/middleware.py`
   - Action: Add `X-Content-Type-Options`, `X-Frame-Options`, `Content-Security-Policy`, `Strict-Transport-Security`.
   - Acceptance: OWASP ZAP scan shows no missing security header warnings.

### Phase 2: Scalability & Infrastructure (Weeks 3–4)
**Goal:** Enable horizontal scaling and production-grade resource management.

5. **Make Redis rate limiter the production default**
   - Files: `uar/api/middleware.py`, `docker-compose.prod.yml`
   - Action: In `create_rate_limiter()`, if `ENVIRONMENT=production` and `REDIS_URL` is set, use `RedisRateLimiter`. Add Redis to docker-compose as a required service.
   - Acceptance: Load test with 4 Uvicorn workers; rate limit is shared across processes.

6. **Add Prometheus `/metrics` endpoint**
   - Files: `uar/api/metrics.py`, `uar/api/server.py`
   - Action: Replace custom `MetricsCollector` with `prometheus-fastapi-instrumentator` or expose existing data at `/metrics` in exposition format.
   - Acceptance: `curl localhost:9090/metrics` returns valid Prometheus text.

7. **Implement graceful shutdown**
   - Files: `uar/api/server.py`, `Dockerfile.prod`
   - Action: Use `asynccontextmanager` lifespan to drain active WebSocket connections and finish in-flight runs on SIGTERM.
   - Acceptance: `docker stop` waits up to 30s for active requests to complete.

8. **Add deep health checks**
   - Files: `uar/api/server.py`
   - Action: `/api/health` checks SQLite writability, Redis connectivity (if configured), and disk space. `/api/ready` returns 503 if any check fails.
   - Acceptance: Kubernetes readiness probe uses `/api/ready`.

### Phase 3: Observability & Developer Experience (Weeks 5–6)
**Goal:** Production debugging, SLOs, and operational confidence.

9. **Add OpenTelemetry tracing**
   - Files: `uar/api/server.py`, `uar/core/executor.py`
   - Action: Instrument FastAPI with `opentelemetry-instrumentation-fastapi`. Add spans for skill execution, recipe expansion, and DB operations.
   - Acceptance: Jaeger UI shows trace trees for `/api/run` requests.

10. **Standardize error response codes**
    - Files: `uar/api/server.py`, `uar/api/middleware.py`
    - Action: Every error response includes `error_code` (e.g., `RATE_LIMIT_EXCEEDED`, `INVALID_SKILL`), `message`, `request_id`, and optional `docs_url`.
    - Acceptance: Frontend can switch on `error_code` without parsing messages.

11. **Create `@requires_package` decorator**
    - Files: `uar/core/registry.py` (new decorator), all skill files
    - Action: `@requires_package("scipy", install_hint="pip install scipy")` replaces boilerplate `importlib.util.find_spec` checks.
    - Acceptance: All 10+ skill files use the decorator; no repeated `find_spec` code.

12. **Add frontend-backend contract testing**
    - Files: `tests/`, CI workflow
    - Action: Generate OpenAPI spec from FastAPI, validate frontend API client against it in CI.
    - Acceptance: CI fails if backend adds a required field without frontend update.

### Phase 4: Operational Maturity (Weeks 7–8)
**Goal:** Enterprise deployment, compliance, and long-term maintainability.

13. **Database migrations with Alembic**
    - Files: New `migrations/`, `uar/objects/store.py`
    - Action: Add Alembic for SQLite schema evolution. Include in Docker entrypoint.
    - Acceptance: `alembic upgrade head` runs successfully on fresh and existing databases.

14. **Secret hot-reload via file watcher**
    - Files: `uar/api/middleware.py`, `uar/config.py`
    - Action: Watch `API_KEYS_FILE` for changes (via `watchdog` or periodic stat). Reload without process restart.
    - Acceptance: Key rotation reflects within 30 seconds.

15. **Add Helm chart for Kubernetes**
    - Files: New `deploy/helm/`
    - Action: Chart with Deployment, HPA, Ingress, ConfigMap, Secret. Support for external Redis and persistent volume for SQLite.
    - Acceptance: `helm install uar ./deploy/helm/uar` produces a running service.

16. **Implement data retention policies**
    - Files: `uar/memory/json_store.py`, `uar/core/executor.py`
    - Action: Configurable TTL on run records. Background job purges old runs based on `RUN_RETENTION_DAYS`.
    - Acceptance: Runs older than TTL are archived or deleted automatically.

---

## 5. Quick Wins (Can be done in < 1 day)

| # | Action | File(s) | Impact |
|---|--------|---------|--------|
| 1 | Fix `parse_request_body` stream consumption | `middleware.py` | Prevent endpoint fragility |
| 2 | Add `__all__` exports to all skill modules | `uar/skills/*.py` | Cleaner imports, fewer symbol leaks |
| 3 | Move inline styles in UARPanel to CSS module | `UARPanel.tsx:2250` | Resolve lint, improve maintainability |
| 4 | Add `docker-compose.override.yml` for local dev | New file | Simplify local onboarding |
| 5 | Add `make test-e2e` target with Playwright scaffold | `Makefile`, `tests/e2e/` | Foundation for E2E testing |
| 6 | Document API with auto-generated OpenAPI HTML | `docs/api.html` | Immediate developer value |

---

## 6. Metrics for Success

Track these KPIs monthly:

- **Security:** Zero `eval()` usage in production skills; 100% OWASP ZAP pass rate.
- **Reliability:** 99.9% uptime (measured via `/api/health` probes); <0.1% error rate.
- **Performance:** p99 latency for `/api/run` < 5s; p99 for `/api/stream` first event < 500ms.
- **Operations:** Mean time to detect (MTTD) < 2 minutes; mean time to resolve (MTTR) < 30 minutes.
- **Developer velocity:** CI pipeline duration < 10 minutes; new skill onboarding time < 30 minutes.

---

## 7. Appendix: Reference Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Ingress / LB                         │
│                  (TLS termination, WAF)                       │
└──────────────────────┬────────────────────────────────────────┘
                       │
        ┌──────────────┼──────────────┐
        │              │              │
   ┌────▼────┐    ┌────▼────┐    ┌────▼────┐
   │ UAR Pod │    │ UAR Pod │    │ UAR Pod │  ← HPA (3-10 replicas)
   │  (API)  │    │  (API)  │    │  (API)  │
   └────┬────┘    └────┬────┘    └────┬────┘
        │              │              │
        └──────────────┼──────────────┘
                       │
              ┌────────▼────────┐
              │   Redis Cluster   │  ← Shared rate limits, caches
              └────────┬────────┘
                       │
              ┌────────▼────────┐
              │  SQLite / Postgres │  ← Run persistence (migrate to PG)
              └─────────────────┘
                       │
              ┌────────▼────────┐
              │  Prometheus/Grafana │  ← Metrics, dashboards, alerts
              └─────────────────┘
```

---

*Prepared for UAR v1.1.0 enterprise readiness initiative.*
