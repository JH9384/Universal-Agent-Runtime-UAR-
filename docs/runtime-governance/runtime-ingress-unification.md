# Runtime Ingress Unification

## Objective

All governed runtime execution enters through RuntimeGateway.

## Unified Execution Path

RuntimeGateway
-> ConstitutionalDispatchPipeline
-> PolicyEngine
-> ExecutionAuthority
-> Executor
-> Replay Engine
-> Runtime Observation
-> Persistence

## Required Runtime Properties

- deterministic replay compatibility
- replay lineage continuity
- replay-safe execution enforcement
- governance-aware dispatch
- runtime-mode validation
- replay drift visibility

## Forbidden Runtime Paths

- direct executor invocation
- bypass dispatch
- replay-unsafe deterministic execution
- execution without replay observation
- execution without replay persistence

## Phase 3B Completion Criteria

- all execution ingress paths routed through RuntimeGateway
- replay validation enforced at ingress
- replay lineage continuity preserved
- authority checks globally enforced
- governance dispatch becomes mandatory
