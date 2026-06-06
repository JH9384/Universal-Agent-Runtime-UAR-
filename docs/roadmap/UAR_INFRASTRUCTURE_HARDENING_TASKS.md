# UAR Infrastructure Hardening — Detailed Task Decomposition

> Subtasks, owners, acceptance criteria, and file mappings for all 12 tasks.

---

## T1 — DI Container: Extract Global Mutable State

**Goal gaps:** G1 (modularity), G6 (store independence), G7 (guarantees)
**Root cause:** `uar/api/state.py` creates services at import time; 19 modules import it.
**Precedents:** None — foundational
**Dependencies:** T2, T3, T5, T7
**Effort:** 3-4 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T1.1 | Create `uar/container.py` with `Container` dataclass | Backend | 4h | Holds `store`, `_auth_svc`, `_event_svc`, `_exec_svc`, `_ws_conn_counter`, `_sse_connections`, `_idempotency_cache`, `_idempotency_lock` |
| T1.2 | Modify `uar/boot.py` to construct `Container` in `BootContext` | Backend | 2h | `create_app()` receives `ctx: BootContext` with injected container |
| T1.3 | Modify `uar/api/server.py` to re-export from container | Backend | 2h | Backward-compatible re-exports preserved during transition |
| T1.4 | Remove lazy imports from `uar/api/routers/streaming.py` | Backend | 2h | Imports `_exec_svc`, `_event_svc` at module level |
| T1.5 | Migrate all `operator/*.py` routers from `state.store` | Backend | 4h | `grep -r "from uar.api.state import store" uar/` returns zero |
| T1.6 | Migrate `core/activity_log.py`, `core/credential_vault.py`, `core/mission_control.py` | Backend | 4h | Core modules never import API layer |
| T1.7 | Update test fixtures to inject `MockRunStore` via container | Backend | 4h | All tests pass without patching `server.store` |
| T1.8 | Deprecate `uar/api/state.py` | Backend | 1h | `import uar.api.state` raises `DeprecationWarning` |
| T1.9 | Full test suite verification | QA | 4h | `pytest tests/ --timeout=120 -q` passes |

**Files created:** `uar/container.py`
**Files modified:** `uar/api/state.py`, `uar/api/server.py`, `uar/boot.py`, `uar/api/routers/streaming.py`, `uar/api/routers/operator/*.py`, `uar/core/activity_log.py`, `uar/core/credential_vault.py`, `uar/core/mission_control.py`, `tests/conftest.py`

---

## T2 — Encryption at Rest

**Goal gaps:** G3, G9, GDPR Art. 32
**Root cause:** All stores write plaintext; temp files unencrypted.
**Precedents:** T1
**Dependencies:** T12
**Effort:** 2 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T2.1 | Add `cryptography` and `sqlcipher3` to dependencies | Backend | 30m | `pyproject.toml` updated |
| T2.2 | Create `uar/crypto.py` with `FernetKeyManager` | Backend | 4h | Key rotation support; `UAR_ENCRYPTION_KEY` env var |
| T2.3 | Wrap `JsonRunStore` with encryption | Backend | 4h | `cat runs/*.jsonl | head -1` shows base64 ciphertext |
| T2.4 | Wrap `SqliteStore` with SQLCipher | Backend | 4h | `hexdump -C uar_runs.db | head -1` shows random bytes |
| T2.5 | Wrap `PostgresRunStore` with app-level encryption | Backend | 4h | Sensitive columns encrypted before INSERT |
| T2.6 | Encrypt temp files in `services/execution.py` | Backend | 2h | Temp file writes encrypted chunks |
| T2.7 | Add key rotation procedure | Security | 2h | Document in `docs/operations/KEY_MANAGEMENT.md` |
| T2.8 | Full test suite verification | QA | 4h | Performance regression < 10% |

**Files created:** `uar/crypto.py`, `docs/operations/KEY_MANAGEMENT.md`
**Files modified:** `uar/memory/json_store.py`, `uar/memory/sqlite_store.py`, `uar/memory/postgres_store.py`, `uar/services/execution.py`, `pyproject.toml`

---

## T3 — Immutable Audit Logs

**Goal gaps:** G2, G3, G4, G9
**Root cause:** Audit logs written to stdout; no external persistence; no tamper-proofing.
**Precedents:** T1
**Dependencies:** T12
**Effort:** 1-2 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T3.1 | Create `uar/audit_shipper.py` with async batch shipper | Backend | 4h | Buffers 100 events or 5s timeout |
| T3.2 | Implement S3 destination with Object Lock | Backend | 4h | Legal hold enabled; bucket versioning on |
| T3.3 | Implement CloudWatch Logs fallback | Backend | 2h | `UAR_AUDIT_DESTINATION=cloudwatch` works |
| T3.4 | Replace `get_audit_logger().write()` with shipper | Backend | 2h | All admin actions ship to external store |
| T3.5 | Add webhook alert shipper integration | Backend | 2h | Failed webhooks also shipped |
| T3.6 | Update `docker-compose.prod.yml` | DevOps | 2h | Includes IAM sidecar docs |
| T3.7 | Add `tests/api/test_audit_shipper.py` | QA | 2h | Verifies shipper receives all events |
| T3.8 | Full test suite verification | QA | 2h | No regression |

**Files created:** `uar/audit_shipper.py`, `tests/api/test_audit_shipper.py`
**Files modified:** `uar/api/routers/operator/common.py`, `uar/core/audit.py`, `docker-compose.prod.yml`

---

## T4 — Separate Testing: Remove testing/ from Production

**Goal gaps:** G3, G9
**Root cause:** `burn_in.py:294` imports `BurnInRunner` from `testing/`.
**Precedents:** None
**Dependencies:** T11
**Effort:** 1 day

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T4.1 | Move `BurnInRunner` to `uar/services/burnin.py` | Backend | 2h | All classes moved; imports updated |
| T4.2 | Update `burn_in.py` router import | Backend | 1h | Imports from `services.burnin` |
| T4.3 | Make `testing/burnin/runner.py` a deprecation wrapper | Backend | 1h | Tests still pass |
| T4.4 | Update `Dockerfile.prod` to exclude tests/ | DevOps | 1h | `ls /app/tests/` returns "No such file" |
| T4.5 | Verify burn-in endpoint | QA | 2h | `POST /api/uar/burnin/run` returns valid report |

**Files created:** `uar/services/burnin.py`
**Files modified:** `uar/api/routers/burn_in.py`, `uar/testing/burnin/runner.py`, `Dockerfile.prod`

---

## T5 — Protocol Boundaries: API to Executor Contract

**Goal gaps:** G1, G10
**Root cause:** `GoalExecutionService` calls `Executor.iter_events()` directly; no serialization.
**Precedents:** T1
**Dependencies:** T6, T10
**Effort:** 3-5 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T5.1 | Define protobuf schema for GoalSpec, Event, RunRecord | Backend | 4h | `.proto` files in `uar/protocol/` |
| T5.2 | Create `uar/protocol/serializer.py` with msgpack fallback | Backend | 2h | `serialize(event)` returns bytes |
| T5.3 | Modify `GoalExecutionService` to publish to Redis Stream | Backend | 4h | Publishes to `uar:goals` with maxlen trimming |
| T5.4 | Create `uar/executor_worker/` consumer loop | Backend | 4h | Subscribes to `uar:goals`; runs `Executor`; publishes events back |
| T5.5 | Add graceful worker shutdown | Backend | 2h | `SIGTERM` completes current goal before exit |
| T5.6 | Add worker health check endpoint | Backend | 2h | `GET :8081/health` returns 200 if running |
| T5.7 | Add Redis Stream consumer group | Backend | 2h | Multiple workers share group; round-robin distribution |
| T5.8 | Integration test: kill worker mid-goal | QA | 4h | API detects worker death; client gets reconnection event |
| T5.9 | Performance benchmark: 100 concurrent goals | QA | 2h | p99 latency < 10s; no event loss |

**Files created:** `uar/protocol/*.proto`, `uar/protocol/serializer.py`, `uar/executor_worker/`
**Files modified:** `uar/services/execution.py`, `uar/core/executor.py`

---

## T6 — Distributed Executor: Real Worker Pool

**Goal gaps:** G1, G10
**Root cause:** `WorkerPool` is `ThreadPoolExecutor` with aspirational RPC comment.
**Precedents:** T5
**Dependencies:** T10
**Effort:** 5-7 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T6.1 | Deprecate `uar/core/distributed.py` | Backend | 1h | Moved or deleted |
| T6.2 | Implement Celery task definitions | Backend | 4h | `@celery_app.task` with retry policy |
| T6.3 | Implement Redis Queue alternative | Backend | 4h | `rq` or `arq` worker; job queue `uar:goals` |
| T6.4 | Add worker autoscaling based on queue depth | DevOps | 4h | HPA targets custom metric; scale 1-10 |
| T6.5 | Add dedicated worker pod spec | DevOps | 2h | CPU limit 2 cores; memory limit 4GB |
| T6.6 | Implement task timeout and cancellation | Backend | 2h | `UAR_WORKER_TIMEOUT=300` default |
| T6.7 | Add worker metrics | Backend | 2h | Prometheus counters per worker |
| T6.8 | Load test: 1,000 WebSocket connections | QA | 4h | No drops; delivery 100%; memory < 1MB/conn |
| T6.9 | Load test: CPU-bound skill isolation | QA | 4h | `scipy_opt` for 30s; health endpoint < 10ms |

**Files created:** `uar/executor_worker/celery_app.py`, `deploy/helm/uar/templates/worker-deployment.yaml`
**Files modified:** `uar/core/distributed.py`, `deploy/helm/uar/values.yaml`

---

## T7 — External Metrics: Prometheus + Grafana

**Goal gaps:** G2, G8
**Root cause:** `MetricsCollector` is custom, in-memory, lost on restart.
**Precedents:** T1
**Dependencies:** T8
**Effort:** 2 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T7.1 | Replace `MetricsCollector` with `prometheus-fastapi-instrumentator` | Backend | 4h | Custom `Histogram` deleted |
| T7.2 | Remove custom `metrics_middleware` | Backend | 2h | Delegates to instrumentator |
| T7.3 | Update `metrics.py` router | Backend | 2h | `GET /api/metrics` returns valid Prometheus format |
| T7.4 | Add skill-level latency histogram | Backend | 2h | `uar_skill_duration_seconds{skill_name}` exported |
| T7.5 | Deploy Prometheus | DevOps | 2h | Scrapes `/api/metrics` every 15s; 90-day retention |
| T7.6 | Deploy Grafana with UAR dashboard | DevOps | 4h | Shows availability, latency, error rate, connections |
| T7.7 | Add `METRICS_API_KEY` protection | Backend | 1h | Optional env var; Bearer required if set |
| T7.8 | Full test suite verification | QA | 2h | `test_metrics.py` passes; dashboard loads |

**Files created:** `deploy/prometheus/prometheus.yml`, `deploy/grafana/dashboards/uar.json`
**Files modified:** `uar/api/metrics.py`, `uar/api/routers/metrics.py`, `uar/api/middleware.py`, `uar/core/executor.py`

---

## T8 — Synthetic Probing + Alerting

**Goal gaps:** G8
**Root cause:** Availability self-reported; no external validation; no PagerDuty.
**Precedents:** T7
**Dependencies:** None
**Effort:** 1-2 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T8.1 | Deploy Blackbox Exporter | DevOps | 2h | Probes `/api/health/live` from 3 regions |
| T8.2 | Configure Alertmanager with PagerDuty | DevOps | 2h | P0 to PagerDuty; P1 to Slack |
| T8.3 | Create runbooks for P0-P3 | SRE | 4h | `docs/runbooks/P0_API_DOWN.md` etc. with `kubectl` commands |
| T8.4 | Add synthetic probe to CI | DevOps | 1h | CI runs probe after deploy |
| T8.5 | Configure UptimeRobot secondary probe | DevOps | 1h | Independent every 60s |
| T8.6 | Add SLA reporting job | DevOps | 2h | Weekly cron; posts to Slack |
| T8.7 | Full integration test | QA | 2h | Kill API container; PagerDuty incident within 5 min |

**Files created:** `deploy/prometheus/blackbox.yml`, `deploy/alertmanager/alertmanager.yml`, `docs/runbooks/P0_API_DOWN.md`, `docs/runbooks/P1_LATENCY_SPIKE.md`, `docs/runbooks/P2_ERROR_RATE.md`, `docs/runbooks/P3_METRICS_MISSING.md`
**Files modified:** `.github/workflows/ci.yml`

---

## T9 — API Normalization: Error Codes + Versioning

**Goal gaps:** G8
**Root cause:** 28 occurrences of `authentication_required` vs `unauthorized`; no API versioning.
**Precedents:** None
**Dependencies:** None
**Effort:** 1-2 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T9.1 | Create `uar/api/errors.py` with `ErrorCode` enum | Backend | 2h | Includes `UNAUTHORIZED`, `FORBIDDEN`, `RATE_LIMITED`, etc. |
| T9.2 | Replace magic strings in middleware | Backend | 2h | `auth_middleware` uses `ErrorCode.UNAUTHORIZED.value` |
| T9.3 | Replace magic strings in endpoint guards | Backend | 4h | All routers use `ErrorCode` enum |
| T9.4 | Add `/api/v1/` router prefix | Backend | 2h | `/api/` returns `Deprecation` header; `/api/v1/` works |
| T9.5 | Update tests to assert `error_code` field | QA | 2h | Zero tests assert `detail.error` string |
| T9.6 | Full test suite verification | QA | 2h | All tests pass |

**Files created:** `uar/api/errors.py`
**Files modified:** `uar/api/middleware.py`, `uar/api/routers/mission_control.py`, `uar/api/routers/burn_in.py`, `uar/api/routers/runs.py`, `uar/api/routers/topology.py`, `uar/api/rbac.py`, `tests/api/test_mission_control_auth.py`, `tests/api/test_trust_spine_fixes.py`, `tests/test_api_contract.py`

---

## T10 — K8s Deployment: Helm Chart

**Goal gaps:** G10, G3
**Root cause:** No Helm chart; `Dockerfile.prod` uses `COPY . .`.
**Precedents:** T5, T6
**Dependencies:** None
**Effort:** 2-3 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T10.1 | Create `Chart.yaml` with dependencies | DevOps | 2h | Version 0.1.0; optional redis, prometheus, grafana |
| T10.2 | Create API server Deployment + Service + Ingress | DevOps | 4h | 3 replicas; RollingUpdate; TLS; PDB |
| T10.3 | Create worker Deployment with HPA | DevOps | 4h | HPA targets CPU 70% or queue depth; max 20 |
| T10.4 | Multi-stage Dockerfile | DevOps | 2h | Final image < 200MB; `USER nonroot` |
| T10.5 | Add resource quotas | DevOps | 2h | API: 500m CPU, 512Mi; worker: 2000m CPU, 4096Mi |
| T10.6 | Add ConfigMap for env vars | DevOps | 1h | `UAR_STORE_BACKEND`, `REDIS_URL` from ConfigMap |
| T10.7 | Add Secret for keys | DevOps | 1h | Kubernetes Secret; optional external-secrets operator |
| T10.8 | Helm install verification | DevOps | 2h | All pods Ready; ingress responds |
| T10.9 | Rolling update verification | QA | 2h | Zero-downtime upgrade |

**Files created:** `deploy/helm/uar/Chart.yaml`, `deploy/helm/uar/values.yaml`, `deploy/helm/uar/templates/*.yaml`
**Files modified:** `Dockerfile.prod`

---

## T11 — SBOM + Supply Chain Scanning

**Goal gaps:** G3, G9, NIS2
**Root cause:** No SBOM; no automated CVE scanning.
**Precedents:** T4
**Dependencies:** None
**Effort:** 4 hours

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T11.1 | Add `anchore/syft` GitHub Action | DevOps | 1h | Generates `sbom.spdx.json` on every release |
| T11.2 | Add `snyk test` to CI | DevOps | 1h | Fails on critical CVE in production deps |
| T11.3 | Add `trivy image` scan to CI | DevOps | 1h | Fails on critical OS-level CVE |
| T11.4 | Update `DEPENDENCY_COMPLIANCE.md` | Docs | 30m | References CI artifacts, not manual table |
| T11.5 | Verify no test-only deps in production | DevOps | 30m | `[project.dependencies]` has zero test-only packages |

**Files created:** `.github/workflows/sbom.yml`
**Files modified:** `.github/workflows/ci.yml`, `docs/DEPENDENCY_COMPLIANCE.md`

---

## T12 — GDPR Compliance

**Goal gaps:** G3, EU market access, EU AI Act
**Root cause:** No Article 17 erasure API; no DPIA.
**Precedents:** T2, T3
**Dependencies:** None
**Effort:** 2 days

### Subtasks

| # | Task | Owner | Effort | Acceptance Criteria |
|---|------|-------|--------|---------------------|
| T12.1 | Create `DELETE /api/v1/runs?user_id={uid}` endpoint | Backend | 4h | Deletes all run records across all backends |
| T12.2 | Implement S3 audit log erasure | Backend | 4h | Retained per policy but marked erased |
| T12.3 | Add confirmation token flow | Backend | 2h | Returns 202 with token; token expires in 1 hour |
| T12.4 | Create `docs/compliance/DPIA.md` | Legal/Security | 4h | Covers data categories, purposes, retention, risks |
| T12.5 | Add Article 30 Register of Processing Activities | Legal/Security | 2h | Spreadsheet of all processing activities |
| T12.6 | Update `SLA.md` with breach notification | Legal | 2h | 72-hour procedure documented |
| T12.7 | Add `tests/api/test_gdpr_erasure.py` | QA | 2h | Verifies records deleted, token flow, cross-backend consistency |
| T12.8 | Full test suite verification | QA | 2h | No regression |

**Files created:** `uar/api/routers/compliance.py`, `docs/compliance/DPIA.md`, `tests/api/test_gdpr_erasure.py`
**Files modified:** `uar/api/routers/runs.py`, `uar/memory/*.py`, `docs/SLA.md`
