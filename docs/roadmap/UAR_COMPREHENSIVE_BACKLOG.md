# UAR Comprehensive Backlog — Single Development Path

> Unified backlog combining all previously captured tasks, infrastructure hardening, deferred items, and operational readiness work into one prioritized development path.
> Generated: 2026-06-05
> Status: READY FOR EXECUTION

---

## How to Read This Document

| Column | Meaning |
|--------|---------|
| **ID** | Unique task identifier (prefix denotes source) |
| **Task** | Description |
| **Source** | Where this task was originally captured |
| **Effort** | Estimated calendar days |
| **Sprint** | Which 2-week sprint this belongs to |
| **Precedents** | Must complete before this task can start |
| **Dependencies** | Tasks this task unblocks |
| **Goal** | Which UAR goal this advances |

**Sprint allocation:**
- Sprint A: Foundation (T1, T4, T9, T11)
- Sprint B: Security & Compliance (T2, T3, T12, E1, E2)
- Sprint C: Observability & SLA (T7, T8, E3, E4)
- Sprint D: Scalability (T5, T6, T10, E5, E6)
- Sprint E: Validation & Hardening (B1-B5, F1-F10, R1-R3)
- Sprint F: Omega-7B.1 Operational Validation (data collection)

---

## Part 1: Infrastructure Hardening (from this session)

| ID | Task | Effort | Sprint | Precedents | Dependencies | Goal |
|----|------|--------|--------|------------|--------------|------|
| **T1** | DI Container: Extract `state.py` globals | 3-4d | A | None | T2, T3, T5, T7 | G1, G6 |
| **T2** | Encryption at Rest: SQLite/Postgres/JSONL | 2d | B | T1 | T12 | G3, G9 |
| **T3** | Immutable Audit Logs: S3/CloudWatch | 1-2d | B | T1 | T12 | G2, G4 |
| **T4** | Separate Testing: Extract BurnInRunner | 1d | A | None | T11 | G3, G9 |
| **T5** | Protocol Boundaries: API to Executor contract | 3-5d | D | T1 | T6, T10 | G1, G10 |
| **T6** | Distributed Executor: Real worker pool | 5-7d | D | T5 | T10 | G1, G10 |
| **T7** | External Metrics: Prometheus + Grafana | 2d | C | T1 | T8 | G2, G8 |
| **T8** | Synthetic Probing: Blackbox + PagerDuty | 1-2d | C | T7 | None | G8 |
| **T9** | API Normalization: Error codes + /api/v1/ | 1-2d | A | None | None | G8 |
| **T10** | K8s Deployment: Helm chart + HPA | 2-3d | D | T5, T6 | None | G10 |
| **T11** | SBOM + Supply Chain: Snyk/Trivy | 4h | A | T4 | None | G3, G9 |
| **T12** | GDPR Compliance: Article 17 erasure + DPIA | 2d | B | T2, T3 | None | G3, EU |

---

## Part 2: Enterprise Sprint Deferred Items (from ENTERPRISE_POST_SCRUM_REVIEW.md)

| ID | Task | Effort | Sprint | Precedents | Dependencies | Goal |
|----|------|--------|--------|------------|--------------|------|
| **E1** | Helm chart for Kubernetes | 1-2d | D | T5, T6 | None | G10 |
| **E2** | Structured audit log shipping | 1d | B | T1 | T12 | G2, G3 |
| **E3** | API versioning (/api/v1/) | 1d | A | None | None | G8 |
| **E4** | Replace parse_request_body stream consumption | 2d | C | T1 | None | G1 |
| **E5** | Move UARPanel inline styles to CSS module | 2h | C | None | None | UX |
| **E6** | Add __all__ exports to all skill modules | 2h | A | None | None | G1 |
| **E7** | Cursor-based pagination for list endpoints | 1d | C | None | None | G10 |
| **E8** | Performance benchmarks in CI (p99 < 5s gate) | 1d | C | T7 | None | G8 |
| **E9** | Multi-stage Dockerfile (exclude tests/docs) | 2h | A | None | T10 | G3 |
| **E10** | Chaos/fault injection tests | 2d | E | T5, T6 | None | G7 |

**Notes:**
- E1 is superseded by T10 (same work, T10 is more comprehensive)
- E2 is superseded by T3 (same work, T3 includes S3 Object Lock)
- E3 is superseded by T9 (same work)
- E9 is included in T10 (multi-stage Dockerfile is T10.4)

---

## Part 3: Operational Validation (from BURN_IN_PLAN.md + FAILURE_INJECTION_PLAN.md)

| ID | Task | Effort | Sprint | Precedents | Dependencies | Goal |
|----|------|--------|--------|------------|--------------|------|
| **B1** | Phase 0: Lock scope (no new features) | 1d | E | T1-T12 | B2-B5 | Process |
| **B2** | Phase 1: Environment baseline verification | 1d | E | B1 | B3 | G7 |
| **B3** | Phase 2A: Planner validation | 1d | E | B2 | B4 | G7 |
| **B3b** | Phase 2B: RuntimeConfig validation | 1d | E | B2 | B4 | G7 |
| **B3c** | Phase 2C: RuntimeEvent validation | 1d | E | B2 | B4 | G7 |
| **B4** | Phase 3A: Replay integrity burn-in | 2d | E | B3 | B5 | G4 |
| **B4b** | Phase 3B: Timeline projection burn-in | 2d | E | B3 | B5 | G4 |
| **B5** | Phase 4A: Runtime trace fixtures | 2d | E | B4 | None | G4 |
| **B5b** | Phase 4B: Replay certification | 2d | E | B4 | None | G4 |
| **F1** | FI-1: Websocket disconnect injection | 4h | E | T5 | None | G7 |
| **F2** | FI-2: Cache purge injection | 4h | E | T5 | None | G7 |
| **F3** | FI-3: Replay stream corruption | 4h | E | T3 | None | G4 |
| **F4** | FI-4: Missing topology node | 4h | E | T5 | None | G7 |
| **F5** | FI-5: Interrupted run | 4h | E | T5 | None | G7 |
| **F6** | FI-6: Partial event loss | 4h | E | T3 | None | G4 |
| **F7** | FI-7: Duplicate terminal event | 4h | E | T3 | None | G4 |
| **F8** | FI-8: Store write failure (transient) | 4h | E | T2 | None | G7 |
| **F9** | FI-9: Snapshot build under extreme memory | 4h | E | T5 | None | G10 |
| **F10** | FI-10: Concurrent burn-in + analytics | 4h | E | T7 | None | G10 |

---

## Part 4: Learning Architecture (from FREEZES_AND_LOCKS.md)

| ID | Task | Effort | Sprint | Precedents | Dependencies | Goal |
|----|------|--------|--------|------------|--------------|------|
| **L1** | Omega-7B.1 Operational Validation: 2-4 week data collection | 4w | F | B1-B5, F1-F10, T1-T12 | None | G4, G5 |
| **L2** | Trust Validation Report #1 generation | 1d | F | L1 | L3 | G4 |
| **L3** | Burn-In Report #1 generation | 1d | F | L1 | L4 | G4 |
| **L4** | Insight Report #1 generation | 1d | F | L1 | None | G5 |
| **L5** | Exit criteria assessment (all 4 metrics) | 1d | F | L2-L4 | None | G4 |

---

## Part 5: Runtime Separation (from UAR_RUNTIME_SEPARATION_AND_OPS_PLAN.md)

| ID | Task | Effort | Sprint | Precedents | Dependencies | Goal |
|----|------|--------|--------|------------|--------------|------|
| **R1** | Mission Control v1: Live execution sessions | 2d | E | T7 | None | G4 |
| **R2** | Replay Explorer v1: Run timeline browsing | 2d | E | T3 | None | G4 |
| **R3** | Runtime Health dashboards | 2d | C | T7 | None | G2 |
| **R4** | Certification report generation | 2d | E | T3 | None | G4 |

---

## Part 6: Bug Fixes (from this session — already fixed)

| ID | Task | Status | Source |
|----|------|--------|--------|
| **BUG-1** | audit_admin_action silent failure | FIXED | `common.py:88-106` |
| **BUG-2** | _parse_ports no-op | FIXED | `verilog_parse.py:44-48` |
| **BUG-3** | _writer_exception poisoning | FIXED | `sqlite_store.py:291` |
| **BUG-4** | _version_lt bare except | FIXED | `self_update.py:119-120` |

---

## Consolidated Sprint Plan

### Sprint A: Foundation (Days 1-10)

**Theme:** Unblock everything else

| Day | Tasks |
|-----|-------|
| 1-3 | **T1** DI Container (T1.1-T1.3) |
| 3-4 | **T1** DI Container migration (T1.4-T1.7) |
| 4 | **T1** Deprecation + test verification (T1.8-T1.9) |
| 4-5 | **T4** Separate Testing (T4.1-T4.5) |
| 5-6 | **T9** API Normalization (T9.1-T9.4) |
| 6 | **T9** Test updates (T9.5-T9.6) |
| 6-7 | **E6** __all__ exports |
| 7 | **E9** Multi-stage Dockerfile |
| 8 | **T11** SBOM + Snyk/Trivy |
| 9-10 | Buffer / review / fix |

**Gates:**
- `grep -r "from uar.api.state" uar/core/` returns zero
- `docker run --rm uar-prod ls /app/tests/` returns "No such file"
- All tests pass without patching `server.store`

---

### Sprint B: Security & Compliance (Days 11-20)

**Theme:** Make data safe and compliant

| Day | Tasks |
|-----|-------|
| 11-12 | **T2** Encryption at Rest (T2.1-T2.4) |
| 12-13 | **T2** Postgres + temp file encryption (T2.5-T2.6) |
| 13 | **T2** Key rotation docs (T2.7) |
| 13-14 | **T2** Test verification (T2.8) |
| 14-15 | **T3** Immutable Audit Logs (T3.1-T3.3) |
| 15-16 | **T3** Integration + CI (T3.4-T3.8) |
| 16-17 | **E2** Structured audit log shipping |
| 17-18 | **T12** GDPR erasure API (T12.1-T12.3) |
| 18-19 | **T12** DPIA + documentation (T12.4-T12.6) |
| 19-20 | **T12** Tests + verification (T12.7-T12.8) |

**Gates:**
- `hexdump -C uar_runs.db | head -1` shows random bytes
- `aws s3 ls s3://uar-audit-logs/` shows dated files
- `DELETE /api/v1/runs?user_id=test` erases and returns confirmation

---

### Sprint C: Observability & SLA (Days 21-30)

**Theme:** See what's happening; enforce commitments

| Day | Tasks |
|-----|-------|
| 21-22 | **T7** External Metrics (T7.1-T7.4) |
| 22-23 | **T7** Prometheus + Grafana deploy (T7.5-T7.7) |
| 23 | **T7** Verification (T7.8) |
| 23-24 | **T8** Blackbox + Alertmanager (T8.1-T8.3) |
| 24-25 | **T8** UptimeRobot + CI + SLA reporting (T8.4-T8.7) |
| 25-26 | **E4** Replace parse_request_body stream consumption |
| 26-27 | **E3** API versioning (already done in T9; verify) |
| 27-28 | **R3** Runtime Health dashboards |
| 28 | **E5** UARPanel CSS module |
| 28-29 | **E7** Cursor-based pagination |
| 29-30 | **E8** Performance benchmarks in CI |

**Gates:**
- `GET /api/metrics` returns historical data
- PagerDuty incident fires within 5 min of simulated API death
- p99 < 5s gate in CI

---

### Sprint D: Scalability (Days 31-40)

**Theme:** Scale horizontally

| Day | Tasks |
|-----|-------|
| 31-33 | **T5** Protocol Boundaries (T5.1-T5.4) |
| 33-34 | **T5** Worker loop + health check (T5.5-T5.7) |
| 34-35 | **T5** Integration tests (T5.8-T5.9) |
| 35-37 | **T6** Distributed Executor (T6.1-T6.3) |
| 37-38 | **T6** Autoscaling + worker spec (T6.4-T6.7) |
| 38-39 | **T6** Load tests (T6.8-T6.9) |
| 39-40 | **T10** K8s Helm chart (T10.1-T10.7) |
| 40 | **T10** Verification (T10.8-T10.9) |

**Gates:**
- Kill worker mid-goal; API detects and reconnects
- 1,000 WebSocket connections sustained for 5 min
- `helm install` deploys successfully with HPA

---

### Sprint E: Validation & Hardening (Days 41-50)

**Theme:** Prove it works under stress

| Day | Tasks |
|-----|-------|
| 41 | **B1** Lock scope |
| 42 | **B2** Environment baseline |
| 43 | **B3** Planner + RuntimeConfig + RuntimeEvent validation |
| 44-45 | **B4** Replay integrity + Timeline projection |
| 45-46 | **B5** Runtime trace fixtures + Replay certification |
| 46-47 | **F1-F5** Failure injection (transient + structural) |
| 47-48 | **F6-F10** Failure injection (data integrity + resource + concurrency) |
| 48-49 | **R1** Mission Control v1 |
| 49-50 | **R2** Replay Explorer v1 + **R4** Certification reports |

**Gates:**
- All 10 failure injections pass without crashing
- Detection times meet targets
- Recovery times meet targets
- `fidelity_score` remains 100%

---

### Sprint F: Omega-7B.1 Operational Validation (Days 51-80)

**Theme:** Let reality vote

| Week | Tasks |
|------|-------|
| Week 1 (51-57) | **L1** Begin 2-4 week data collection; ENABLE_TRUST_RANKING=false (observation mode) |
| Week 2 (58-64) | **L1** Continue data collection; monitor trust distribution |
| Week 3 (65-71) | **L1** Continue data collection; measure ranking delta |
| Week 4 (72-78) | **L1** Complete data collection; verify outcome correlation |
| 79 | **L2-L4** Generate Trust, Burn-In, Insight reports |
| 80 | **L5** Exit criteria assessment; go/no-go for Omega-7c |

**Go/No-Go Criteria (ALL must pass):**
1. Trust Stability: < 0.10 week-over-week
2. Calibration Stability: < 0.05 week-over-week
3. Ranking Stability: Top-5 types consistent, < 20% band changes weekly
4. Resolution Correlation: Spearman >= 0.3 (minimum), 0.5 (preferred)

---

## Dependency Graph (Unified)

```text
Sprint A (Foundation)
  T1 ───────────────────────────────────┐
  T4 ──> T11                            │
  T9                                    │
  E6                                    │
  E9                                    │
                                        │
Sprint B (Security)                     │
  T2 ──> T12 <──────────────────────────┤
  T3 ───┘                               │
  E2                                    │
                                        │
Sprint C (Observability)                │
  T7 ──> T8                             │
  E4                                    │
  R3                                    │
  E5                                    │
  E7                                    │
  E8                                    │
                                        │
Sprint D (Scalability)                  │
  T5 ──> T6 ──> T10                     │
                                        │
Sprint E (Validation)                   │
  B1 ──> B2 ──> B3 ──> B4 ──> B5      │
  F1-F10 (parallel with B*)           │
  R1, R2, R4                            │
                                        │
Sprint F (Omega-7B.1)                  │
  L1 (4 weeks) ──> L2-L5                │
```

---

## Risk-Adjusted Timeline

| Scenario | Duration | Condition |
|----------|----------|-----------|
| **Optimistic** | 10 weeks | T1 completes in 2 days; no test regressions |
| **Expected** | 12 weeks | Standard pace; minor setbacks |
| **Pessimistic** | 14 weeks | T1 test rewrite takes full 4 days; Redis protocol issues |

**Buffer recommendation:** Plan for 12 weeks, aim for 10.

---

## Part 7: Business Opportunities (New — Not Previously Captured)

> These opportunities emerge only after T1-T12 infrastructure hardening is complete. They represent potential revenue streams and strategic positioning beyond the core runtime.

---

### OP1 — UAR as Compliance Engine for External AI Systems

| Attribute | Value |
|-----------|-------|
| **Description** | Package Trust Spine, Burn-In Framework, and Certification Engine as standalone compliance validation service for non-UAR AI systems |
| **Target customers** | Enterprises using LangChain, CrewAI, OpenAI API needing SOC 2 / EU AI Act compliance |
| **Revenue model** | Compliance-as-a-Service — per-certification report fee |
| **Prerequisites** | T3 (immutable audit), T12 (GDPR), B1-B5 (validation framework), F1-F10 (failure injection proven) |
| **Effort** | 2-3 months |
| **Market timing** | EU AI Act enforcement begins 2026; first-mover advantage |
| **Key differentiator** | Only platform with pre-built Omega-2/Omega-3/Omega-7B.1 certification artifacts |

**Implementation path:**
1. Extract `uar/core/certification.py` into standalone `uar-compliance` package
2. Add adapters for LangChain chains, OpenAI function calls, CrewAI crews
3. Build `POST /api/v1/compliance/certify` endpoint accepting external execution traces
4. Generate PDF/JSON certification reports with digital signatures
5. Partner with SOC 2 auditors as distribution channel

---

### OP2 — Sell Omega-7B.1 Dataset

| Attribute | Value |
|-----------|-------|
| **Description** | License the 4-week trust validation dataset to AI researchers and benchmark organizations |
| **Target customers** | Academic researchers, AI benchmark organizations (MLPerf, HELM), enterprise AI evaluators |
| **Revenue model** | Data licensing — per-researcher or per-organization annual license |
| **Prerequisites** | L1 (4-week data collection complete), T3 (immutable audit ensures data integrity), T2 (encryption ensures safe transfer) |
| **Effort** | 1 month (packaging + legal + distribution) |
| **Market timing** | Dataset is irreplaceable once collected; scarcity creates value |
| **Key differentiator** | First-of-kind longitudinal agent trust dataset with ground-truth outcomes |

**Dataset contents:**
- Trust score evolution per skill type (50+ types, 4 weeks, 15-min granularity)
- Skill latency distributions (p50/p95/p99 per skill, per hardware config)
- Failure injection outcomes (10 injection types × 100 runs each)
- Outcome correlation matrix (trust score vs. resolution success)
- Calibration error time series (bucket-level week-over-week)

**Implementation path:**
1. Sprint F: Execute L1 data collection with full telemetry
2. Anonymize user identifiers (hash with salt)
3. Package as Parquet + documentation + academic citation guide
4. List on AI data marketplaces (Hugging Face Datasets, Kaggle)
5. Offer enterprise licensing with SLA for updates

---

### OP3 — Agent Runtime Middleware Platform

| Attribute | Value |
|-----------|-------|
| **Description** | Position UAR as the standard runtime platform that all AI frameworks execute on — the "Kubernetes of agent runtimes" |
| **Target customers** | Framework authors (LangChain, CrewAI, AutoGen), enterprise platform teams |
| **Revenue model** | Platform fee per execution; enterprise support contracts |
| **Prerequisites** | T5 (protocol boundaries), T6 (distributed executor), T10 (K8s), R1-R4 (operator tools) |
| **Effort** | 6 months |
| **Market timing** | No incumbent exists; fragmentation creates demand for standardization |
| **Key differentiator** | Only runtime with built-in trust scoring, replay, and certification |

**Value proposition per framework:**
| Framework | UAR Adds |
|-----------|----------|
| LangChain | Persistence, replay, distributed execution, trust scoring |
| CrewAI | Horizontal scaling, mission control, certification |
| AutoGen | Event streaming, WebSocket/SSE real-time, audit trail |
| Dify/LangFlow | Production-grade backend, RBAC, encryption |

**Implementation path:**
1. Define standardized skill interface (`uarskill` spec — inputs, outputs, events)
2. Build plugin SDK (`pip install uar-sdk`) with local dev server
3. Create framework adapters (LangChain → UAR, CrewAI → UAR)
4. Launch developer portal with docs, examples, certification guide
5. Host public skill marketplace (npm-for-agents model)

---

### OP4 — UAR as Skill Hosting Platform

| Attribute | Value |
|-----------|-------|
| **Description** | External developers upload skills via API; UAR sandboxes, registers, and executes them with billing |
| **Target customers** | AI developers, ML engineers, domain experts (verilog, legal, medical) |
| **Revenue model** | Marketplace fee per execution; revenue share with skill authors |
| **Prerequisites** | T1 (DI container enables sandboxing), T2 (encryption isolates tenants), T4 (clean prod/test boundary), T12 (GDPR handles user data) |
| **Effort** | 3-4 months |
| **Market timing** | GitHub Copilot extensions show demand; no agent-native marketplace exists |
| **Key differentiator** | Built-in trust scoring — consumers see skill reliability before purchase |

**Implementation path:**
1. Build `PluginService` accepting WASM/Python packages
2. Add sandbox isolation (gVisor, Firecracker, or restricted Python)
3. Implement skill approval workflow (automated + manual)
4. Add billing meter per skill execution
5. Expose `GET /api/v1/marketplace/skills` with trust scores

---

### OP5 — Synthetic Data Generation Service

| Attribute | Value |
|-----------|-------|
| **Description** | Package UAR's 127-skill execution traces as structured synthetic datasets for model training and benchmarking |
| **Target customers** | AI training data buyers, model evaluators, software verification teams |
| **Revenue model** | Data-as-a-Service — per-million-record fee |
| **Prerequisites** | T5 (protocol boundaries enable parallel generation), T7 (metrics track generation throughput), B1-B5 (validated execution correctness) |
| **Effort** | 2 months |
| **Market timing** | Demand for high-quality synthetic training data exceeds supply |
| **Key differentiator** | Ground-truth validated via UAR's Burn-In Framework |

**Dataset offerings:**
| Skill | Synthetic Output | Use Case |
|-------|------------------|----------|
| `verilog_parse` | Parsed ASTs from RTL | Chip design ML training |
| `scipy_opt` | Optimization convergence traces | Reinforcement learning |
| `doc_ingest` | Structured extractions | RAG benchmark datasets |
| `riscv_sim` | Instruction execution traces | CPU design verification |
| `graphrag_skills` | Knowledge graph triples | Graph neural network training |

**Implementation path:**
1. Add batch execution API (`POST /api/v1/batch/generate` with parameter sweeps)
2. Build data pipeline: execution → anonymization → Parquet export
3. Create dataset catalog with quality metrics (Burn-In validated)
4. Integrate with Hugging Face Datasets, Kaggle, AWS Data Exchange

---

### OP6 — Operator Copilot Standalone Product

| Attribute | Value |
|-----------|-------|
| **Description** | Package Mission Control, Trust Ranking, and Replay Explorer as standalone "AgentOps" product |
| **Target customers** | AI operations teams, MLOps engineers, platform teams |
| **Revenue model** | SaaS — per-seat or per-agent-month |
| **Prerequisites** | R1-R4 (operator tools complete), T7 (external metrics), T8 (synthetic probing) |
| **Effort** | 2-3 months |
| **Market timing** | AgentOps is emerging category; no clear leader |
| **Key differentiator** | Only tool with built-in trust computation and replay debugging |

**Product modules:**
| Module | Description | Competitor Gap |
|--------|-------------|----------------|
| **AgentOps Dashboard** | Real-time agent monitoring | Datadog doesn't understand agent semantics |
| **TrustScore API** | `GET /trust?agent_id=` reliability score | No competitor computes trust from outcomes |
| **DebugAI** | Step-through replay of LLM chains | No competitor has event-level replay |
| **CertifyAI** | Automated validation report generation | Manual pen-test only in market |

**Implementation path:**
1. Extract `apps/operator-dashboard/` into standalone Next.js app
2. Add multi-tenant backend (separate from UAR runtime)
3. Build agent adapter SDK (instrument any agent framework)
4. Launch on AWS Marketplace / Azure Marketplace
5. Partner with consulting firms (McKinsey, BCG) for enterprise rollout

---

### OP7 — Technical Debt as Open Source IP

| Attribute | Value |
|-----------|-------|
| **Description** | Extract UAR's custom components as standalone open-source libraries; open-core revenue model |
| **Target customers** | Python developers, FastAPI users, multi-tenant SaaS builders |
| **Revenue model** | Open-core: free library + paid enterprise features |
| **Prerequisites** | T1 (clean separation enables extraction), T9 (stable API contract) |
| **Effort** | 1 month per library |
| **Market timing** | Community hungry for lightweight alternatives to heavy dependencies |
| **Key differentiator** | Battle-tested in production with 127-skill workload |

**Library candidates:**
| UAR Component | Standalone Library | Enterprise Paid Feature |
|---------------|-------------------|------------------------|
| DDSketch histogram | `uar-metrics` | Prometheus auto-scrape, Grafana templates |
| `safe_eval.py` | `safe-expr` | AST policy editor, audit trail |
| Event streaming bridge | `fastapi-events` | WebSocket clustering, backpressure management |
| Skill registry | `skill-registry` | RBAC, versioning, marketplace integration |
| Rate limiter | `fastapi-limiter` | Redis cluster, geo-distributed rate limiting |

**Implementation path:**
1. Extract each component into separate repo with CI/CD
2. Publish to PyPI with permissive license (MIT/Apache)
3. Build enterprise feature set ( encryption, audit, RBAC)
4. Launch on GitHub with comprehensive docs and examples
5. Offer paid support contracts for enterprise users

---

### OP8 — Regulatory Moat (EU AI Act + NIS2)

| Attribute | Value |
|-----------|-------|
| **Description** | Position UAR's certification artifacts as pre-built compliance evidence for EU AI Act and NIS2 |
| **Target customers** | European enterprises, AI vendors selling into EU, compliance consultancies |
| **Revenue model** | Compliance subscription — annual fee for artifact generation + updates |
| **Prerequisites** | T2 (encryption), T3 (immutable audit), T12 (GDPR + DPIA), B1-B5 (validation), F1-F10 (resilience proven) |
| **Effort** | 2 months (documentation + API + legal review) |
| **Market timing** | EU AI Act enforcement begins 2026; penalties up to 4% global revenue |
| **Key differentiator** | Only platform with operational validation evidence (Omega-2/3/7B.1) |

**Compliance mapping:**
| Regulation | Requirement | UAR Evidence |
|------------|-------------|--------------|
| EU AI Act Art. 9 | Risk management system | Burn-In Framework + Failure Injection Plan |
| EU AI Act Art. 10 | Data governance | Replay Explorer + data lineage |
| EU AI Act Art. 13 | Transparency | Trust Ranking API + explainability scores |
| EU AI Act Art. 14 | Human oversight | Mission Control + alert system |
| NIS2 Art. 23 | Supply chain security | SBOM (T11) + Snyk/Trivy scanning |
| GDPR Art. 32 | Security of processing | Encryption (T2) + access controls |
| GDPR Art. 17 | Right to erasure | Erasure API (T12) + DPIA documentation |

**Implementation path:**
1. Map each UAR artifact to specific regulation article
2. Generate compliance report template (auto-populated from UAR data)
3. Build `GET /api/v1/compliance/report?regulation=eu_ai_act` endpoint
4. Partner with EU law firms for distribution
5. Apply for EU AI Act "regulatory sandbox" participation

---

## Opportunity Dependency Graph

```text
T1-T12 Infrastructure Hardening (Sprints A-D)
  ├──> B1-B5 + F1-F10 Validation (Sprint E)
  │     └──> L1 Omega-7B.1 Data Collection (Sprint F)
  │           ├──> OP2 (Dataset licensing)
  │           └──> OP8 (Regulatory artifacts)
  │
  ├──> R1-R4 Operator Tools (Sprint E)
  │     └──> OP6 (AgentOps standalone)
  │
  ├──> T5 + T6 + T10 Scalability (Sprint D)
  │     └──> OP3 (Middleware platform)
  │     └──> OP4 (Skill hosting platform)
  │
  ├──> T1 + T9 Clean API (Sprint A)
  │     └──> OP7 (Open source libraries)
  │
  └──> T2 + T3 + T12 Security (Sprint B)
        └──> OP1 (Compliance engine)
        └──> OP5 (Synthetic data — data integrity)
```

---

## Unified Priority Matrix

### Phase 1: Foundation (Weeks 1-10) — NO REVENUE
**Sprint A:** T1, T4, T9, T11, E6, E9
- Focus: Technical debt, clean architecture
- Output: Injectable services, clean boundaries, SBOM

### Phase 2: Security (Weeks 11-20) — NO REVENUE
**Sprint B:** T2, T3, T12, E2
- Focus: Compliance readiness, data protection
- Output: Encrypted stores, immutable audit, GDPR erasure API

### Phase 3: Observability (Weeks 21-30) — NO REVENUE
**Sprint C:** T7, T8, E4, R3, E5, E7, E8
- Focus: External validation, SLA enforcement
- Output: Prometheus, Grafana, PagerDuty, health dashboards

### Phase 4: Scalability (Weeks 31-40) — NO REVENUE
**Sprint D:** T5, T6, T10, E1, E10
- Focus: Horizontal scaling, K8s deployment
- Output: Protocol boundaries, distributed executor, Helm chart

### Phase 5: Validation (Weeks 41-50) — NO REVENUE
**Sprint E:** B1-B5, F1-F10, R1, R2, R4
- Focus: Prove correctness under stress
- Output: Certified resilience, Mission Control v1, Replay Explorer v1

### Phase 6: Trust Data Collection (Weeks 51-80) — NO REVENUE
**Sprint F:** L1 (4 weeks), L2-L5
- Focus: Generate canonical trust dataset
- Output: Trust Validation Report, Burn-In Report, Insight Report

### Phase 7: Revenue Enablement (Weeks 81+) — REVENUE BEGINS
**Sprints G+:** OP1-OP8
- Focus: Monetize infrastructure investment
- Output: Compliance engine, dataset licensing, middleware platform, skill marketplace

---

## Investment Thesis Summary

| Phase | Duration | Cost | Revenue | Cumulative ROI |
|-------|----------|------|---------|----------------|
| 1-6 (Infrastructure) | 20 weeks | High (engineering) | Zero | Negative |
| 7 (Revenue) | Ongoing | Medium (sales/marketing) | High (enterprise) | Positive |

**The bet:** 20 weeks of infrastructure investment creates an **uncloneable moat**:
- Immutable 4-week trust dataset (scarcity)
- Pre-built compliance artifacts (regulatory timing)
- Certified resilience under failure injection (trust)
- Horizontal scaling with K8s (enterprise readiness)

**Competitors can clone features. They cannot clone 20 weeks of validated operational data.**

---

## Single Development Path Summary

1. **Sprint A:** Foundation — DI container, separate testing, API normalization, SBOM
2. **Sprint B:** Security — Encryption, immutable audit, GDPR compliance
3. **Sprint C:** Observability — Prometheus, Grafana, synthetic probing, health dashboards
4. **Sprint D:** Scalability — Protocol boundaries, distributed executor, K8s deployment
5. **Sprint E:** Validation — Burn-in, failure injection, Mission Control, Replay Explorer
6. **Sprint F:** Trust Validation — 4-week Omega-7B.1 data collection and assessment
7. **Sprint G+:** Revenue Enablement — Compliance engine, dataset licensing, middleware platform, skill marketplace, AgentOps, open-source IP, regulatory moat

**The path is sequential at the sprint level but parallel within sprints.** No sprint can start until the previous sprint's gates pass. Omega-7B.1 cannot begin until all infrastructure hardening is complete. Revenue opportunities cannot begin until Omega-7B.1 data is collected.

**The 20-week infrastructure phase is the price of admission. The revenue phase is why the price is worth paying.**
