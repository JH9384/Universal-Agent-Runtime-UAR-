# UAR Infrastructure Hardening — Gap-Fit Matrix

> Each task mapped to specific goal gaps with evidence from the codebase.

---

## G1 — Modular Architecture

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| Global `state.py` imported by 19 modules | `grep -r "from uar.api.state" uar/` returns 19 files | Zero core→API layer imports | **T1** (DI Container) | Extract globals into `Container` dataclass; inject via constructor |
| Circular deps worked around by lazy imports | `streaming.py:95` imports inside function to avoid circular | All imports at module level | **T1** | Clean layer separation eliminates circular dependency |
| "Distributed" executor is just ThreadPoolExecutor | `distributed.py:100` comment "Can be extended to use remote workers via RPC" | Real distributed execution | **T5** (Protocol) + **T6** (Distributed) | Define message contract + implement real worker pool |

---

## G2 — Observable Workflows

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| Metrics in-memory, lost on restart | `metrics.py:22` `_redis_client: Any = None`; lazy Redis | External metrics persist across restarts | **T7** (External Metrics) | Replace custom collector with `prometheus-fastapi-instrumentator`; deploy Prometheus |
| Audit logs swallowed silently (fixed) | `common.py:88,106` had `except Exception: pass` | All failures logged visibly | **T3** (Immutable Audit) | Ship to S3/CloudWatch with Object Lock; no silent swallowing |
| `_parse_ports` silently returns `[]` | `verilog_parse.py:44-48` function body is `return ports` | All skill data validated | Bug fix (no task ID) | Already fixed in this session; test coverage added |
| No synthetic probing | `SLA.md:91` "No synthetic probing" | External availability validation | **T8** (Synthetic Probing) | Blackbox Exporter + UptimeRobot + PagerDuty |

---

## G3 — Production-Ready

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| No encryption at rest | `json_store.py:19` "simple, portable, easy to inspect" (plaintext) | Encrypted stores | **T2** (Encryption) | SQLCipher for SQLite; Fernet for JSONL; app-level for Postgres |
| Production imports `testing/` | `burn_in.py:294` imports `BurnInRunner` from `testing/` | Clean prod/test boundary | **T4** (Separate Testing) | Move `BurnInRunner` to `services/`; Dockerfile excludes tests |
| No secret provider | `middleware.py:405-444` loads API keys from env/file only | Vault/AWSSM integration | **T10** (K8s) | Helm chart includes `external-secrets` operator for secret provider |
| No Helm chart | `ENTERPRISE_POST_SCRUM_REVIEW.md:70` "Deferred — out of scope" | Kubernetes deployment | **T10** (K8s) | Helm chart with HPA, resource quotas, multi-stage Dockerfile |
| No SBOM | `DEPENDENCY_COMPLIANCE.md` manual tracking | Automated SBOM + CVE scanning | **T11** (SBOM) | Syft + Snyk + Trivy in CI |

---

## G4 — Trust Spine

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| Burn-in uses test code | `burn_in.py:294` imports from `testing/` | Production burn-in service | **T4** (Separate Testing) | `BurnInRunner` in `services/` generates trust evidence |
| Certification artifacts in-memory | `certification.py` generates reports but no external storage | Immutable certification artifacts | **T3** (Immutable Audit) | Certification reports shipped to S3 with Object Lock |
| `certify_replay` detects structure not content | `OMEGA_3:68-72` "Replay Consistency != Content Authenticity" | Content integrity verification | **T3** (Immutable Audit) | Content hash chain in audit trail enables authenticity check |
| `_writer_exception` per-process | `sqlite_store.py:291` poisoned state doesn't propagate across workers | Cross-worker error visibility | **T1** (DI Container) | Injectable state enables shared error propagation |

---

## G5 — Operational Intelligence

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| Analytics built on in-memory metrics | `metrics.py` in-memory only | Analytics on persisted time-series | **T7** (External Metrics) | Prometheus provides historical time-series for Grafana dashboards |
| Insights derived from self-reported data | No external validation of metrics | Insights correlated with external probes | **T8** (Synthetic Probing) | UptimeRobot data validates API availability independently |

---

## G6 — Store Independence

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| 19 modules import global `store` | `analytics.py:15`, `incidents.py:18`, etc. import `state.store` | Store injected, never imported directly | **T1** (DI Container) | All consumers receive store via constructor; no global imports |
| Tests patch `server.store` | `test_trust_spine_fixes.py` (18 references) patches module names | Tests inject mock store | **T1** (DI Container) | `conftest.py` provides `container_fixture` with `MockRunStore` |

---

## G7 — Strong Guarantees

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| `_writer_exception` per-process under multi-worker | `sqlite_store.py:291` — one worker's poisoned state hidden from others | Cross-worker error propagation | **T1** (DI Container) | Shared state container enables error visibility |
| Guarantees tested in single-process only | CI runs single-process `pytest` | Multi-worker validation | **T1** + **T5** + **T10** | DI enables testable separation; protocol enables multi-process; K8s enables multi-pod |
| SQLite writer thread drops events silently | `sqlite_store.py:291` `_writer_exception` check | All write failures visible | **T3** (Immutable Audit) | Audit shipper captures all events; no silent drops |

---

## G8 — SLA Compliance

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| Availability self-reported | `SLA.md:91` "No synthetic probing" | External availability validation | **T8** (Synthetic Probing) | Blackbox Exporter + UptimeRobot from 3 regions |
| Metrics lost on restart | `metrics.py:22` `_redis_client` lazy and optional | Persistent metrics | **T7** (External Metrics) | Prometheus scrapes and stores independently |
| No alert wiring | `SLA.md:92` "No alert wiring" | Automated escalation | **T8** (Synthetic Probing) | Alertmanager → PagerDuty for P0; Slack for P1 |
| Dual 401 error codes | `middleware.py:665-714` vs `mission_control.py:66-72` | Single canonical error vocabulary | **T9** (API Normalization) | `ErrorCode` enum; all endpoints use same constants |
| No API versioning | `ENTERPRISE_POST_SCRUM_REVIEW.md:114` "No API versioning" | Versioned API with deprecation path | **T9** (API Normalization) | `/api/v1/` prefix; `/api/` returns `Deprecation` header |

---

## G9 — Security Hardening

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| No encryption at rest | All stores plaintext | Encrypted at rest | **T2** (Encryption) | SQLCipher + Fernet + app-level encryption |
| No immutable audit logs | `common.py:88,106` swallowed exceptions | Tamper-proof audit trail | **T3** (Immutable Audit) | S3 Object Lock + CloudWatch Logs |
| Static API keys | `middleware.py:405-444` loads from env/file | Short-lived tokens or mTLS | **T10** (K8s) | Secret provider integration via `external-secrets` |
| Production imports `testing/` | `burn_in.py:294` | Clean dependency boundary | **T4** (Separate Testing) | No production imports from `testing/` |
| No SBOM/CVE scanning | `DEPENDENCY_COMPLIANCE.md` manual tracking | Automated supply chain security | **T11** (SBOM) | Syft + Snyk + Trivy in CI |

---

## G10 — Scalability

| Gap | Evidence | Target | Task | How Task Closes It |
|-----|----------|--------|------|-------------------|
| Single-process executor | `execution.py:496` `executor = Executor()` in same process | Separable executor | **T5** (Protocol) | Redis Stream message contract between API and executor |
| No horizontal scaling path | `distributed.py:100` aspirational RPC comment | Real distributed workers | **T6** (Distributed) | Celery/RQ worker pool with queue-based distribution |
| No K8s deployment | `ENTERPRISE_POST_SCRUM_REVIEW.md:70` deferred | Kubernetes-native deployment | **T10** (K8s) | Helm chart with HPA, resource quotas |
| SQLite writer contention under multi-worker | `state.py` global store; each worker spawns writer thread | Worker-safe persistence | **T1** (DI Container) + **T5** (Protocol) | DI enables per-worker store instances; protocol enables separate worker processes |

---

## Cross-Goal Compound Risks

| Combination | Risk | Tasks That Address It |
|-------------|------|----------------------|
| Global state + No encryption + No immutable audit | Compromised process reads all history, modifies state, erases tracks | **T1** + **T2** + **T3** |
| Monolithic architecture + Self-reported SLA + No probing | System down for real users while metrics show green | **T5** + **T7** + **T8** |
| Silent failures + No-op parsers + Testing imports production | Bugs accumulate invisibly; test suite passes; real workflows fail | **T1** + **T3** + **T4** + Bug fixes |
| Dual error codes + No API versioning + No contract tests | API surface becomes inconsistent; breaking changes accidental | **T9** |
