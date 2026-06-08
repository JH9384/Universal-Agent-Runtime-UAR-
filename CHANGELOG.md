# Changelog

All notable changes to Universal Agent Runtime are documented here.

This project uses semantic versioning for release tags.

## [Unreleased] — Ω-7B.1 Operational Validation

Phase transition: 2026-06-01

UAR has entered the **Validation Phase**. Phases A–F and all Trust Spine
phases (T1–T6) are complete. The system is classified as an
**Operational Intelligence Platform**. No new components will be added
until Ω-7B.1 exit criteria are met.

**Feature Freeze: ACTIVE**
**Learning Architecture Freeze v1: ACTIVE**

See [docs/FREEZES_AND_LOCKS.md](docs/FREEZES_AND_LOCKS.md) for the canonical registry of all freezes, locks, and directional decisions.

### Added

- **D4A — Operational Optimization**
  - D4A-0: Raised analytics endpoint default limit from 1,000 to 50,000 runs; no silent truncation.
  - D4A-1: Materialized `AnalyticsCache` with 60s TTL and cache invalidation on new runs; median latency < 10ms at 10,000 runs (cache warm).
  - D4A-2: Consolidated `/api/uar/topology/hot-paths` and `/api/uar/topology/failure-hotspots` into `/api/uar/topology/analytics?mode=success|failure`; removed recipe table from topology, linked to Recipe Intelligence.
  - D4A-3: Alert Banner in `UARPanel` surfaces critical/warning alerts from `/api/uar/alerts/summary`; dismissible with 24h TTL.
  - D4A-4: Deep Linking — failure cluster and hotspot responses include `latest_run_id`; rendered as clickable links that open `ReplayExplorer`.
  - D4A-5: Progressive Disclosure Tabs — `MissionControlWidget` reorganized into 5 tabs (Health, Trends, Failures, Topology, Intelligence) with localStorage persistence.

- **D4B — Automation**
  - Alert-to-tab routing: each alert in `/api/uar/alerts/summary` carries a `tab` field; clicking the Alert Banner opens Mission Control directly on the relevant tab.
  - Alert dismiss TTL: dismissed alerts auto-expire after 24 hours so new issues resurface.

- **Hardening Backlog (completed)**
  - #85 Runtime Health Query Consolidation — `RuntimeSnapshot` single-pass store read shared across `score_runtime_health` and `build_snapshot`.
  - #86 Burn-In Persistence Layer — `BurnInProxy.from_latest()` recovers from `uar_metadata` table after restart; `_set_latest_report()` persists via `SqliteRunStore.put_metadata()`.
  - #87 Certification Engine Refactor — removed `contract_compliance`; aligned weights to Trust Spine model (Replay 40%, Burn-In 35%, Runtime Health 25%).

- **D4C — Fleet Operations**
  - D4C-0: Fleet Heartbeat & Registry — `POST /api/uar/fleet/heartbeat`, `GET /api/uar/fleet/nodes`, `GET /api/uar/fleet/health`. In-memory registry with 5-minute TTL, persisted to `uar_metadata`.
  - D4C-1: Cross-Node Health Dashboard — `FleetHealthWidget` component in `UARPanel` showing node grid, fleet health score, critical nodes, and certification distribution. Toolbar button opens fleet view.
  - D4C-2: Fleet-Wide Failure Correlation — `GET /api/uar/fleet/failures` correlates failure clusters by skill across nodes. Surfaces fleet-wide hotspots when same skill fails on >= 3 nodes. Heartbeat accepts optional `failure_clusters` payload.
  - D4C-3: Skill Routing Hints — `GET /api/uar/fleet/routing?skill=<skill>` ranks nodes by health (40%), skill availability (30%), and recent failure history (30%). Penalises nodes with open circuit breakers or known skill failures.

- **D4C — Operator Loop, Recurrence, and Evidence Preview (pending validation)**
  - Added reuse-first operator loop: Briefing → Focus → Fleet Signal / Recurrence → Replay → Outcome Capture → Evidence Pack Preview.
  - Added `MissionControlSnapshot.incident_summary` from existing run records, outcomes, recommendation metadata, and trust engine inputs.
  - Added incident recurrence intelligence without an incident store or incident console.
  - Added `IncidentRecurrenceSummary` surfacing in existing Briefing and Focus panels.
  - Added compact recurrence notes for scope, latest run, incident context, recommendation context, and evidence refs.
  - Added Evidence Pack v2 fleet and incident evidence sections.
  - Added recurrence-aware Evidence Pack preview inside the existing Artifacts tab.
  - Added client-side Evidence Markdown copy and download support; no backend report endpoint added.
  - Added focused D4C validation workflow, CI validation log artifact capture, `make validate-d4c`, `make d4c-result`, and `make d4c-release-gate`.
  - Added release-readiness, validation-lock, promotion-checklist, and release-notes draft docs for D4C.

- **Infrastructure Hardening (T1–T12)**
  - T1: DI Container — `uar.core` modules no longer import from `uar.api.state`. `_uar_start_time` canonicalised in `uar.config`. Go/No-Go Gate G1 enforced by regression test.
  - T2: Encryption at Rest — `EncryptedRunStore` wrapper transparently encrypts JSON blob columns (skills, events, outputs, metadata, uor_witness) and metadata values using Fernet (AES-128-CBC + HMAC). Enabled via `UAR_ENCRYPTION_KEY`. Backwards-compatible with plaintext data.
  - T3: Immutable Audit Logs — `AuditLogger` enhanced with SHA-256 hash chain (`prev_hash` per record). Optional S3 (`UAR_AUDIT_S3_BUCKET`) and CloudWatch (`UAR_AUDIT_CLOUDWATCH_GROUP`) shipping via soft boto3 dependency. `GET /api/uar/admin/audit/verify` endpoint detects tampering.
  - T4: Separate Testing — `uar burn-in run` CLI command added to `uar/cli/main.py`. Runs the same `BurnInRunner` as `POST /api/uar/burnin/run` but without the API server. Supports `--mode=direct` (in-process) and `--mode=http` (remote). `--json` for CI/CD pipelines. Exit code 1 on failure.
  - T5: Protocol Boundaries — `ExecutionGateway` formalises the API-to-Executor contract in `uar/api/gateway.py`. The router (`runs.py`) no longer imports `SimplePlanner`, `Executor`, or `_build_goal` directly. All execution flows through `gateway.execute(RunRequest) → RunRecord`. Side effects (idempotency, store persistence, analytics cache invalidation, sync monitor) are encapsulated in the gateway.
  - T6: Distributed Executor — `WorkerPool` abstraction added in `uar/core/worker_pool.py`. Supports `thread` (default), `process`, and `local` modes. Configurable via `UAR_POOL_MODE` and `UAR_POOL_MAX_WORKERS`. `Executor` accepts optional `pool` argument; `ExecutionGateway` passes it through. Replaces ad-hoc `ThreadPoolExecutor` creation per parallel group with a persistent, injectable pool.
  - T7: External Metrics — `uar_uptime_seconds` gauge added to Prometheus exposition format. New Grafana operational dashboard (`deploy/grafana/dashboards/uar-operational.json`) with panels for uptime, request rate, error rate, request duration p50/p99, skill execution count, and skill errors. Dashboard provisioning updated to generic "UAR Dashboards". Prometheus scrapes `/metrics` at 30s; Grafana auto-configures Prometheus datasource.
  - T8: Synthetic Probing — `SyntheticProbe` in `uar/observability/synthetic_probe.py` probes health, metrics, and OpenAPI endpoints. Consecutive-failure gating (`UAR_PROBE_CONSECUTIVE`, default 2) before alerting. `PagerDutyNotifier` in `uar/observability/pagerduty.py` sends trigger/resolve events via PagerDuty Events API v2 with deterministic dedup keys. CLI: `uar probe run --once --url=<url>` for one-shot checks; `--pagerduty` to enable alerting. Exit code 1 if any probe fails.
  - T9: API Normalization — Standardized response envelopes in `uar/api/responses.py`: `success_response` wraps payloads in `{data: ...}`, `list_response` adds pagination metadata, `error_response` and `error_detail_response` normalize errors to `{error, message, code, request_id, field}`. `ErrorResponse` model updated to match. `APIVersionMiddleware` injects `X-API-Version` header on every response. Exception handlers refactored to use the normalized helpers. Health router (`uar/api/routers/health.py`) migrated as the reference implementation.
  - T10: K8s Deployment — `deploy/k8s/` contains production-ready manifests: Namespace, ServiceAccount (`automountServiceAccountToken: false`), ConfigMap, Secret, Deployment (rolling updates, liveness/readiness probes on `/api/health/{live,ready}`, topology spread constraints), ClusterIP Service, Ingress (TLS via cert-manager), HPA (CPU+memory autoscaling 2–10 replicas), and NetworkPolicy (default-deny with explicit allow rules). Kustomize overlay at `kustomization.yaml` with image substitution. Security defaults: non-root user (UID 999), dropped capabilities, `runAsNonRoot: true`. Offline validation tests in `tests/api/test_k8s_manifests.py`.
  - T11: SBOM + Supply Chain — `uar/observability/sbom.py` generates CycloneDX 1.5 SBOMs from installed packages via `importlib.metadata`. Includes pURL, optional SHA-256 hash from `RECORD`, and validation (`validate_sbom`). CLI: `uar sbom generate --output=sbom.json`. Feed the output into Grype, Trivy, or Snyk for vulnerability scanning.
  - T12: GDPR Compliance — `uar/core/gdpr.py` provides `GDPRController` with `export_data()` (portability), `erase_data()` (right to erasure), and `policy_metadata()`. Privacy API endpoints: `GET /api/uar/privacy/policy` (open), `GET /api/uar/privacy/export` (auth-required), `DELETE /api/uar/privacy/erase` (auth-required). Integrates with existing `RunStoreProtocol.delete()` and retention purge loop.
  - E7: Cursor-based Pagination — `uar/api/pagination.py` adds `encode_cursor` / `decode_cursor` / `paginate_cursor` helpers using opaque `last_id` cursors (base64 JSON). `list_response` extended with `next_cursor`. `GET /api/uar/runs` migrated to cursor pagination with `?cursor=&limit=` query params (default limit=20, max=100). Handles missing cursors gracefully. Tests in `tests/api/test_api_pagination.py`.

### Ω-7B.1 Validation Targets

- Trust Distribution — natural spread across Highly Trusted / Trusted / Watch / Weak bands
- Ranking Delta — cases where confidence and trust disagree
- Outcome Correlation — Spearman ≥ 0.3 (minimum), ≥ 0.5 (preferred)
- Drift Discovery — high-trust types showing negative drift

Exit criteria: trust stability < 0.10 WoW, calibration stability < 0.05 WoW,
ranking stability < 20% band changes weekly, resolution correlation ≥ 0.3.

### Hardening Backlog (all resolved 2026-06-05)

- [x] #85 Runtime Health Query Consolidation — `RuntimeSnapshot` single-pass pattern
- [x] #86 Burn-In Persistence Layer — `put_metadata`/`get_metadata` on `SqliteRunStore`
- [x] #87 Certification Engine Refactor — Trust Spine weights, no `contract_compliance`

---

## [1.2.0-operational-intelligence] — Operational Intelligence Platform Complete

Date: 2026-06-01
Commit: c9dbf25
Test suite: 4322 passed, 13 skipped

All six operational intelligence phases (A–F) are complete. UAR is now an
end-to-end system: execution generates evidence, evidence establishes trust,
trust drives operational intelligence, intelligence surfaces actionable
operator insight.

### Phase G — Operational Evidence Pack (Ω-G.5)

- Security hardening for all operator workflow endpoints
- Navigation refactor: operator dashboard restructured into cohesive sections
- Router decomposition: `operator_workflows.py` split into 11 focused sub-routers
  (`morning_briefing`, `trust_explorer`, `incident_workbench`, `knowledge_graph`,
  `time_machine`, `topology`, `patterns`, `evolution`, `workflows`, `clusters`,
  `intelligence`) for maintainability and testability
- Operational evidence pack: structured evidence bundles for all major operator flows

### Phase F — Insight Generation (Ω-Phase F, commit 30571a1)

- Pattern Recognition: cross-run pattern extraction with frequency and confidence scoring
- Evolution Tracking: longitudinal skill and recipe performance trends
- Workflow Intelligence: automated workflow quality assessment and recommendations
- Cluster Analysis: skill co-occurrence and performance cluster detection
- Operational Intelligence: synthesized insight layer aggregating all Phase F outputs
- 12 new API endpoints under `/api/uar/insights/`

### Phase E — Operational Search & Investigation (Ω-Phase E, commit 82a29e8)

- Operational Search: full-text and structured search across run history
- Investigation Replay: step-through replay with contextual annotation
- Graph Analytics: topology-aware analytics (bottleneck detection, critical path, fan-out)
- 9 new API endpoints under `/api/uar/search/` and `/api/uar/graph/`

### Phase D — Operational Analytics (Ω-T7, commits a083431, 5f7f8b3, b58b0d1)

- Recommendation Inbox: actionable operator recommendations with trust-weighted ranking
- Investigation Flow: guided incident investigation with evidence chain
- Graph v2: enhanced topology visualization with trust overlay
- Report Viewer: structured operational reports with evidence attachment
- Operator Workflows: Morning Briefing, Trust Explorer, Incident Workbench,
  Knowledge Graph Time Machine
- Trust overlay: `ENABLE_TRUST_RANKING` flag; soft blend (0.7 confidence + 0.3 trust)
- Alert persistence: alert state survives process restarts

### Test Coverage

- Expanded test suite from 3721 → 4322 tests (+601)
- All Trust Spine regression tests passing
- Bug fixes: E1 (executor coalesce lock), E2 (RISC-V `_enc_r` rs1 field),
  E3 (RISC-V `_enc_s` bit-field overlap), S1 (sqlite_store writer exception isolation),
  T1 (safe_utils traceback preservation), P1/P2 (postgres async column selection),
  BD (batch deduplicator insertion order)

## [1.1.0-construction] — Trust Spine Construction Complete

Date: 2026-05-31
Test suite: 3721 passed, 1 pre-existing failure (yolo_detect)

### Added

- T1 Replay Confidence: `uar/core/replay_confidence.py` — score 0-100,
  tier, warnings, evidence report
- T2 Runtime Health: `uar/core/runtime_health.py` — component health
  scoring (execution, skills, events, streaming, pressure)
- T3 Burn-In Framework: `uar/testing/burnin/` — contracts, scenarios
  (direct + HTTP modes), `BurnInRunner`
- T4 Certification Engine: `uar/core/certification.py` — Gold/Silver/
  Experimental levels from T1/T2/T3 evidence
- T5 Mission Control: `uar/core/mission_control.py` — operator snapshot
  aggregating all Trust Spine evidence
- T6 Replay Explorer: `uar/api/routers/replay_explorer.py` — per-run
  bundle (timeline, confidence, failure path, events)
- API routers for all phases mounted under `uor_router`
- 48 Trust Spine tests across T1–T6

### Fixed (P0 hardening)

- `BurnInProxy` extracted to `burn_in.py` as single shared class;
  removed 3 duplicate inline definitions from other routers
- `_latest_report` is now written via `_set_latest_report()` under
  `threading.RLock`; concurrent `POST /burnin/run` cannot corrupt state
- Dead per-endpoint auth guards removed from runtime_health,
  certification, and mission_control routers (uor_router already
  enforces `require_auth` globally via boot.py dependency injection)
- `replay_explorer` now enforces per-run ownership check; admins bypass
- `timeline_from_record`, `score_replay`, `run_record_from_dict`
  promoted to module-level imports in `replay_explorer.py`
- 22 regression tests added in `tests/api/test_trust_spine_fixes.py`

## [1.0.0-foundation] — Initial Foundation Release

Date: 2026-05-27
Test suite: 118 passed

### Added

- Initial UOR-aligned execution runtime
- Skill registry and execution DAG
- Structured event logging and run records
- Simple planner and executor
- FastAPI runtime server with `/api/uar/run`, `/api/uar/runs`, `/api/uar/skills`, `/api/health/live`, `/api/health/ready`, `/metrics`
- Replay support via persisted run events
- JSONL-backed run store
- Initial CLI (`uar --help`, `uar init`, `uar run`)
