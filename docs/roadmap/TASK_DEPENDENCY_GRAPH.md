# Task Dependency Graph

> Precedents and dependencies for all 12 infrastructure hardening tasks.

---

## Task Overview

| ID | Task | Effort | Priority |
|----|------|--------|----------|
| T1 | DI Container | 3-4 days | P0 |
| T2 | Encryption at Rest | 2 days | P0 |
| T3 | Immutable Audit Logs | 1-2 days | P0 |
| T4 | Separate Testing | 1 day | P0 |
| T5 | Protocol Boundaries | 3-5 days | P0 |
| T6 | Distributed Executor | 5-7 days | P1 |
| T7 | External Metrics | 2 days | P1 |
| T8 | Synthetic Probing | 1-2 days | P1 |
| T9 | API Normalization | 1-2 days | P1 |
| T10 | K8s Deployment | 2-3 days | P1 |
| T11 | SBOM + Supply Chain | 4 hours | P2 |
| T12 | GDPR Compliance | 2 days | P1 |

---

## Dependency Table

### T1 — DI Container

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | None | Foundational; no task must complete before T1 |
| **Dependencies** | T2 | Stores must be injectable before wrapping with encryption |
| | T3 | Audit logger must be injectable before shipping externally |
| | T5 | Services must be separable before defining protocol contract |
| | T7 | Metrics collector must be injectable before replacing with Prometheus |

**Blocked if T1 delayed:** T2, T3, T5, T7 (67% of task graph)

---

### T2 — Encryption at Rest

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T1 | Store instances must be injectable (not module globals) to wrap with encryption layer |
| **Dependencies** | T12 | Encryption must exist for GDPR erasure to be meaningful (erasing unencrypted data is trivial) |

**Blocked if T1 delayed:** Cannot start until T1 completes

---

### T3 — Immutable Audit Logs

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T1 | Audit logger must be injectable (not global stdout) to ship to external store |
| **Dependencies** | T12 | Immutable audit trail must exist for GDPR accountability and breach investigation |

**Blocked if T1 delayed:** Cannot start until T1 completes

---

### T4 — Separate Testing

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | None | Parallel to T1; no architectural dependency |
| **Dependencies** | T11 | SBOM scanning needs clean dependency graph (test deps excluded from production artifact) |

**Can start immediately** — independent of T1

---

### T5 — Protocol Boundaries

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T1 | GoalExecutionService and Executor must be separable (via DI) before defining message contract |
| **Dependencies** | T6 | Distributed executor needs a protocol contract to implement worker communication |
| | T10 | K8s deployment needs separable components (API vs worker) to deploy independently |

**Blocked if T1 delayed:** Cannot start until T1 completes

---

### T6 — Distributed Executor

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T5 | Message contract (protobuf/serialization) must exist before implementing worker that uses it |
| **Dependencies** | T10 | K8s HPA needs real worker processes to scale (scaling threads in a single pod is not horizontal scaling) |

**Blocked if T5 delayed:** Cannot start until T5 completes

---

### T7 — External Metrics

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T1 | Metrics collector must be injectable (not module global) before replacing with Prometheus instrumentator |
| **Dependencies** | T8 | Synthetic probing needs a metrics pipeline to store and query availability/latency data |

**Blocked if T1 delayed:** Cannot start until T1 completes

---

### T8 — Synthetic Probing

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T7 | Prometheus metrics pipeline must exist before probes can validate and alert on them |
| **Dependencies** | None | Operational enforcement layer; no downstream architectural dependency |

**Blocked if T7 delayed:** Cannot start until T7 completes

---

### T9 — API Normalization

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | None | Self-contained; does not modify service architecture |
| **Dependencies** | None | UX improvement; no downstream blockers |

**Can start immediately** — independent of T1

---

### T10 — K8s Deployment

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T5 | API and Executor must be protocol-separated to deploy as independent pods |
| | T6 | Real worker pool must exist for HPA to scale (autoscaling threads is not horizontal scaling) |
| **Dependencies** | None | Operational endpoint; no downstream tasks |

**Blocked if T5 or T6 delayed:** Cannot start until both complete

---

### T11 — SBOM + Supply Chain

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T4 | Production dependency graph must be clean (no test imports) before SBOM is meaningful |
| **Dependencies** | None | Compliance artifact; no downstream blockers |

**Blocked if T4 delayed:** Can start before T4 but SBOM will include test dependencies inaccurately

---

### T12 — GDPR Compliance

| Direction | Task | Why |
|-----------|------|-----|
| **Precedents** | T2 | Data must be encrypted at rest before erasure API is meaningful (erasing plaintext is trivial) |
| | T3 | Immutable audit trail must exist for GDPR accountability and post-erasure verification |
| **Dependencies** | None | Market access gate; no downstream architectural dependency |

**Blocked if T2 or T3 delayed:** Cannot start until both complete

---

## Critical Paths

### Path A: Security & Compliance (GDPR)

```
T1 ──> T2 ──> T12
  └─> T3 ──┘
```

**Duration:** 7-8 calendar days  
**Gates:** Encryption + Audit Logs → GDPR erasure API + DPIA

---

### Path B: Observability & SLA

```
T1 ──> T7 ──> T8
```

**Duration:** 5-7 calendar days  
**Gates:** DI Container → Prometheus → Synthetic Probing + PagerDuty

---

### Path C: Horizontal Scaling

```
T1 ──> T5 ──> T6 ──> T10
```

**Duration:** 10-16 calendar days  
**Gates:** DI Container → Protocol Boundaries → Distributed Executor → K8s + HPA

---

### Path D: Parallel Quick Wins

```
T4 ──> T11        (Supply Chain Security)
T9                (API Stability)
```

**Duration:** 1-2 calendar days  
**Can run in parallel with T1 and each other**

---

## Visual Dependency Graph

```text
                    +--------+     +--------+     +--------+
    (independent)     |  T4    | --> |  T11   |     |  T9    |
                    +--------+     +--------+     +--------+
                          |
                          v
                    +--------+
                    |   T1   |<-----------------------+
                    +--------+                        |
                          |                         |
           +--------------+--------------+          |
           |              |              |            |
           v              v              v            |
      +--------+    +--------+    +--------+        |
      |   T2   |    |   T3   |    |   T5   |        |
      +--------+    +--------+    +--------+        |
           |              |              |            |
           v              v              v            |
      +--------+    +--------+    +--------+        |
      |  T12   |    | (T12)  |    |   T6   |        |
      +--------+    +--------+    +--------+        |
                                       |             |
                                       v             |
                                  +--------+          |
                                  |  T10   |          |
                                  +--------+          |
                                       ^              |
                                       |              |
                    +--------+         |              |
                    |   T7   |---------+              |
                    +--------+                         |
                         |                             |
                         v                             |
                    +--------+                         |
                    |   T8   |-------------------------+
                    +--------+
```

---

## Blocker Analysis

| If this task is delayed... | These tasks are blocked | Impact |
|---------------------------|------------------------|--------|
| **T1 (DI Container)** | T2, T3, T5, T7 | 67% of task graph blocked; architectural foundation missing |
| **T2 (Encryption)** | T12 | GDPR compliance blocked; cannot enter EU market |
| **T3 (Audit Logs)** | T12 | GDPR accountability blocked; post-incident investigation impossible |
| **T4 (Separate Testing)** | T11 (quality degraded) | SBOM includes test dependencies; supply chain scan noisy |
| **T5 (Protocol)** | T6, T10 | Horizontal scaling blocked; K8s deployment meaningless |
| **T6 (Distributed)** | T10 | K8s HPA has nothing to scale |
| **T7 (Metrics)** | T8 | Synthetic probing has no data pipeline |
| **T8 (Probing)** | None | No downstream blockers but SLA remains unenforceable |
| **T9 (Normalization)** | None | Independent UX improvement |
| **T10 (K8s)** | None | Operational endpoint |
| **T11 (SBOM)** | None | Compliance artifact |
| **T12 (GDPR)** | None | Market access gate |

---

## Parallel Workstreams

| Workstream | Tasks | Can Start | Requires |
|------------|-------|-----------|----------|
| **Foundation** | T1 | Immediately | Nothing |
| **Security Quick Win** | T4, T11 | Immediately | Nothing |
| **UX Polish** | T9 | Immediately | Nothing |
| **Security & Compliance** | T2, T3, T12 | After T1 | T1 |
| **Observability** | T7, T8 | After T1 | T1 |
| **Platform Scaling** | T5, T6, T10 | After T1 | T1 |

**Maximum parallelization:** 6 workstreams with 4 starting immediately (T1, T4, T11, T9)
