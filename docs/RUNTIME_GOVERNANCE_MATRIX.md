# Runtime Governance Matrix

| Layer | Responsibility | Enforcement |
|---|---|---|
| RuntimeMode | execution topology | runtime authority |
| PolicyEngine | execution legality | policy enforcement |
| ReplayJudge | replay admissibility | replay judiciary |
| RunCertificate | portable runtime trust | certification |
| ArtifactLineage | provenance tracking | lineage validation |
| ExecutionAuthority | execution gate | mandatory dispatch control |

## Runtime Flow

```text
Goal
  -> Planner
  -> Governance
  -> Policy
  -> ExecutionAuthority
  -> Executor
  -> ReplayCertification
  -> RunCertificate
```

## Enforcement Direction

Future mandatory gates:

- replay drift rejection
- semantic instability rejection
- governance bypass prevention
- lineage corruption rejection
- topology mismatch rejection

## Strategic Objective

Convert UAR into:

Deterministic Operational Runtime Infrastructure
