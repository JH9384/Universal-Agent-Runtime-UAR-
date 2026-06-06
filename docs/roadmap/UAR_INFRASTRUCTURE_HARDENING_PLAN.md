# UAR Infrastructure Hardening Plan

> Canonical plan for fixing the measurement apparatus before Omega-7B.1 Operational Validation.
> Generated: 2026-06-05
> Status: READY FOR REVIEW
> Blocking: Omega-7B.1 Trust Validation (2-4 week data collection)

---

## Executive Summary

UAR has completed Phases A-F (Runtime to Insight Generation). The Learning Architecture Freeze v1 is active. Omega-7B.1 Operational Validation is the next phase. However, the measurement apparatus that will generate the canonical 2-4 week validation dataset is **architecturally unsound**.

This plan captures 12 infrastructure tasks (T1-T12) that are **permitted under the freeze** (bug fixes, instrumentation, operational validation tooling) and must be completed **before** Omega-7B.1 begins. Running validation now would generate corrupt data that must be discarded after fixes.

**Estimated calendar time:** 6-8 weeks  
**Estimated engineering effort:** 4-5 person-weeks  
**Risk if skipped:** 4 weeks of validation data becomes garbage; all trust formula tuning is trained on noise.

---

## The Twelve Tasks

| ID | Task | Goal Gaps | Precedents | Dependencies | Effort | Priority |
|----|------|-----------|------------|--------------|--------|----------|
| **T1** | DI Container: Extract state.py globals | G1, G6, G7 | None | T2, T3, T5, T7 | 3-4 days | P0 |
| **T2** | Encryption at Rest: SQLite/Postgres/JSONL | G3, G9, GDPR | T1 | T12 | 2 days | P0 |
| **T3** | Immutable Audit Logs: S3/CloudWatch | G2, G3, G4, G9 | T1 | T12 | 1-2 days | P0 |
| **T4** | Separate Testing: Extract BurnInRunner | G3, G9 | None | T11 | 1 day | P0 |
| **T5** | Protocol Boundaries: API to Executor contract | G1, G10 | T1 | T6, T10 | 3-5 days | P0 |
| **T6** | Distributed Executor: Real worker pool | G1, G10 | T5 | T10 | 5-7 days | P1 |
| **T7** | External Metrics: Prometheus + Grafana | G2, G8 | T1 | T8 | 2 days | P1 |
| **T8** | Synthetic Probing: Blackbox + PagerDuty | G8 | T7 | None | 1-2 days | P1 |
| **T9** | API Normalization: Error codes + /api/v1/ | G8 | None | None | 1-2 days | P1 |
| **T10** | K8s Deployment: Helm chart + HPA | G10 | T5, T6 | None | 2-3 days | P1 |
| **T11** | SBOM + Supply Chain: Snyk/Trivy scanning | G3, G9, NIS2 | T4 | None | 4 hours | P2 |
| **T12** | GDPR Compliance: Article 17 erasure + DPIA | G3, EU market | T2, T3 | None | 2 days | P1 |

---

## Sprint Allocation

| Sprint | Tasks | Goals Closed | Team Size | Calendar Days |
|--------|-------|--------------|-----------|---------------|
| **Sprint 1** | T1, T4, T9, T11 | G1, G6, G8, G9 partial | 2 backend + 1 DevOps | 10 |
| **Sprint 2** | T2, T3, T12 | G2, G3, G4, G9, GDPR | 2 backend + 1 security + 1 legal | 10 |
| **Sprint 3** | T5, T7 | G1, G2, G10 partial | 2 backend + 1 DevOps | 10 |
| **Sprint 4** | T6, T8, T10 | G1, G8, G10 | 2 backend + 1 DevOps + 1 SRE | 10 |

**Total:** 40 calendar days (6-8 weeks with buffer)

---

## Dependency Graph

```
T1 (DI Container) --------------------> T2 (Encryption) --> T12 (GDPR)
       |                                   |
       |---> T3 (Audit Logs) ---------------+
       |
       |---> T5 (Protocol) --> T6 (Distributed) --> T10 (K8s)
       |
       +---> T7 (Metrics) --> T8 (Probing)

T4 (Separate Testing) --> T11 (SBOM)

T9 (API Normalization)  (independent)
```

**Critical path:** T1 -> T2 -> T12 = 7-8 days to GDPR compliance  
**Critical path:** T1 -> T5 -> T6 -> T10 = 10-16 days to horizontal scaling

---

## Go/No-Go Gates for Omega-7B.1

| Gate | Check | Owner |
|------|-------|-------|
| G1 | `grep -r "from uar.api.state" uar/core/` returns zero | Backend |
| G2 | `GET /api/metrics` returns historical data (not just since restart) | DevOps |
| G3 | `docker run --rm uar-prod ls /app/tests/` returns "No such file" | DevOps |
| G4 | Burn-in endpoint uses `uar.services.burnin`, not `testing` | QA |
| G5 | `hexdump -C uar_runs.db | head -1` shows encrypted data | Security |
| G6 | `aws s3 ls s3://uar-audit-logs/` shows dated files with legal hold | DevOps |
| G7 | PagerDuty incident fires within 5 min of simulated API death | SRE |
| G8 | Synthetic probe logs show 3-region availability > 99.5% | SRE |
| G9 | `helm install` deploys successfully with HPA | DevOps |
| G10 | 1,000 concurrent WebSocket connections sustained for 5 min | QA |
| G11 | SBOM attached to latest release; Snyk scan clean | Security |
| G12 | `DELETE /api/v1/runs?user_id=test` erases and returns confirmation | Legal |

**All 12 gates must pass before Omega-7B.1 begins.**

---

## Why This Is Not New Building

The Learning Architecture Freeze v1 permits:
- Bug fixes
- Instrumentation additions
- Documentation updates
- Dashboard visualizations
- Operational validation tooling

Every task in this plan falls into the **permitted** categories:

| Task | Freeze Category |
|------|-----------------|
| T1 (DI Container) | Instrumentation — makes metrics injectable and testable |
| T2 (Encryption) | Operational validation tooling — ensures data integrity for audit |
| T3 (Immutable Audit) | Instrumentation — makes Trust Spine auditable |
| T4 (Separate Testing) | Bug fix — removes production/test boundary violation |
| T5 (Protocol Boundaries) | Operational validation tooling — enables distributed testing |
| T6 (Distributed Executor) | Operational validation tooling — enables load testing at scale |
| T7 (External Metrics) | Instrumentation — replaces self-reporting with external truth |
| T8 (Synthetic Probing) | Operational validation tooling — validates SLA claims independently |
| T9 (API Normalization) | Bug fix — fixes error code inconsistency |
| T10 (K8s Deployment) | Operational validation tooling — enables staging environment |
| T11 (SBOM Scanning) | Operational validation tooling — supply chain validation |
| T12 (GDPR Compliance) | Operational validation tooling — market access validation |

---

## Risk Register

| ID | Risk | Probability | Impact | Mitigation |
|----|------|-------------|--------|------------|
| R1 | T1 breaks test patching pattern; major test rewrite | Medium | High | Preserve backward-compatible re-exports during transition |
| R2 | T2 encryption causes >10% performance regression | Medium | Medium | Benchmark before/after; consider WAL mode + async I/O |
| R3 | T5 introduces Redis as required dependency | Medium | Medium | Provide FakeRedis/moto mock for local dev |
| R4 | T6 adds operational complexity (broker, DLQ) | Medium | High | Start with Redis Streams before Celery; add DLQ handler |
| R5 | T10 Helm chart needs cluster-specific tuning | High | Low | Document required values; provide examples for EKS/GKE/AKS |
| R6 | Calendar slip pushes into Omega-7B.1 window | Medium | High | Parallel workstreams; T1 and T4 can start immediately |

---

## Files Referenced

| File | Relevance |
|------|-----------|
| `uar/api/state.py` | Root cause of global mutable state (T1) |
| `uar/api/routers/burn_in.py:294` | Production imports testing (T4) |
| `uar/api/middleware.py:665-714` | Dual 401 error codes (T9) |
| `uar/memory/sqlite_store.py:291` | `_writer_exception` per-process (T1) |
| `uar/skills/verilog_parse.py:44-48` | No-op `_parse_ports` (bug fix, no task ID) |
| `uar/services/execution.py:519-521` | `run_in_executor` thread bridge (T5) |
| `uar/core/distributed.py:100` | Aspirational RPC comment (T6) |
| `uar/api/metrics.py:22-39` | In-memory metrics (T7) |
| `docs/SLA.md:91-93` | Self-reported metrics gap (T7, T8) |
| `docs/ENTERPRISE_POST_SCRUM_REVIEW.md:14` | Security 9/10 claim (T2, T3) |
| `docs/FREEZES_AND_LOCKS.md` | Learning Architecture Freeze v1 |
| `docs/certification/OMEGA_3_OPERATIONAL_VALIDATION.md:68-72` | Replay consistency vs authenticity (T3) |

---

## Related Documents

- `docs/roadmap/UAR_INFRASTRUCTURE_HARDENING_TASKS.md` — Detailed task decomposition with subtasks, owners, acceptance criteria
- `docs/roadmap/UAR_INFRASTRUCTURE_HARDENING_GAPS.md` — Gap-fit matrix: each task mapped to specific goal gaps with evidence
- `docs/roadmap/UAR_INFRASTRUCTURE_HARDENING_RISKS.md` — Full risk register with mitigation plans and escalation paths
