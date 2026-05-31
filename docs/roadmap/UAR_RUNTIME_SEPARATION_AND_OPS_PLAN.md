# UAR Runtime Separation and Operations Plan

## Objective

Establish a stable operational baseline before introducing major new capabilities.

Primary goals:

1. Preserve UAR as a deterministic runtime.
2. Separate runtime concerns from workloads.
3. Expand Mission Control and Replay capabilities.
4. Improve observability and certification readiness.
5. Enable future Xarvus/Codex integration without coupling.

---

## Current Assessment

Strengths:

- Strong event-driven runtime.
- Replayable execution model.
- Skill registry abstraction.
- Recipe orchestration.
- WebSocket streaming.
- Metrics and observability foundation.

Risks:

- Executor concentration.
- Runtime and workload boundaries are blurred.
- Scientific compute and agent functions share the same operational surface.
- Replay Explorer is present in pieces but not yet a first-class product.

---

## Target Architecture

### Layer 1: Runtime Core

- Contracts
- Event schema
- Executor kernel
- Scheduler
- Replay validation

### Layer 2: Runtime Services

- Cache
- Metrics
- Persistence
- Audit
- UOR addressing

### Layer 3: Workloads

- Skills
- Recipes
- Agent systems
- Scientific computing
- External integrations

### Layer 4: Operations

- Mission Control
- Runtime Health
- Replay Explorer
- Certification Reports
- Topology Visualization

---

## Immediate Burn-In Work

### Mission Control

- Live execution sessions
- Runtime health panel
- Event stream inspection
- Metrics overview

### Replay Explorer

- Run timeline browsing
- Event reconstruction
- Failure-path inspection
- Recipe expansion visualization

### Runtime Health

- Skill latency tracking
- Cache effectiveness
- Retry visibility
- WebSocket health

### Certification

- Long-duration burn-in runs
- Runtime stability reports
- Replay consistency checks
- Event contract validation

---

## 30 Day Focus

1. Documentation completion.
2. Replay Explorer v1.
3. Mission Control v1.
4. Runtime health dashboards.
5. Certification report generation.

---

## Success Criteria

UAR becomes:

- Operationally observable.
- Replayable.
- Certifiable.
- Modular.
- Ready for future Xarvus and Codex adapters.
