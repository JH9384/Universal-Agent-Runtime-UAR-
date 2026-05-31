# Runtime Guarantees Specification

Status: Specification  
Trust Spine Phase: T2  
Primary Issue: #69  
Related Issue: #68

## Purpose

Runtime Guarantees convert observed implementation behavior into explicit operator and developer expectations.

Guarantees are classified so UAR can distinguish between strong contracts, best-effort behavior, and experimental assumptions.

## Guarantee Classes

### Strong

A Strong guarantee is expected to hold under normal operation and should be testable.

### Best Effort

A Best Effort guarantee is intended behavior but can be affected by transport, environment, configuration, or external dependencies.

### Experimental

An Experimental guarantee is under active development and should not yet be used as a certification requirement.

## Candidate Strong Guarantees

### Run Identity

Every persisted run has a unique `run_id` that identifies the run across API, storage, replay, and operator views.

Validation:

- run id exists
- run id is stable across retrieval
- run id maps to one persisted record

### Run Reconstruction

A persisted `RunRecord` can be reconstructed from supported stores using the store abstraction.

Validation:

- JSONL reconstruction
- SQLite reconstruction
- Postgres reconstruction
- invalid rows degrade safely

### Store Independence

Runtime consumers should not need to know which backend stores run records.

Validation:

- API outputs are backend-agnostic
- replay functions consume `RunRecord`, not backend rows

### Replay Derivability

Replay artifacts are derivable from persisted run events.

Validation:

- replay summary exists
- timeline can be generated
- confidence can be calculated

## Candidate Best-Effort Guarantees

### Streaming Delivery

Connected SSE/WebSocket clients should receive structured runtime events while connected.

Limitations:

- network drops
- client disconnects
- backpressure
- server restart

### Metrics Continuity

Runtime metrics should be available during normal service operation.

Limitations:

- process restart
- metrics backend failure
- environment configuration

### Operator View Freshness

Mission Control should represent the current known runtime state, but may lag live execution due to transport and aggregation latency.

## Candidate Experimental Guarantees

### Certification Reproducibility

Certification outputs should be reproducible from the same evidence bundle.

Requires:

- stable scoring model
- stable evidence schema
- deterministic aggregation

### Cross-Store UOR Provenance Consistency

UOR address and witness metadata should remain consistent across all run stores.

Requires:

- schema normalization
- migration support
- store-level validation

## Validation Matrix

| Guarantee | Class | Validation Source |
| --- | --- | --- |
| Run Identity | Strong | Store/API tests |
| Run Reconstruction | Strong | Store/replay tests |
| Store Independence | Strong | Backend parity tests |
| Replay Derivability | Strong | Replay confidence tests |
| Streaming Delivery | Best Effort | Streaming tests |
| Metrics Continuity | Best Effort | Metrics tests |
| Certification Reproducibility | Experimental | Certification tests |
| UOR Provenance Consistency | Experimental | Store/UOR tests |

## Consumers

- Replay Confidence
- Burn-In Framework
- Certification Scoring
- Certification Engine
- Mission Control
- Replay Explorer

## v1 Success Criteria

Runtime Guarantees v1 is complete when:

- guarantee classes are documented
- validation criteria exist
- guarantee failures produce warnings or evidence gaps
- certification scoring can reference guarantee status
