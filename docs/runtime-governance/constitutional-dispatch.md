# Constitutional Dispatch Invariants

## Principle

No runtime execution should occur outside the ConstitutionalDispatchPipeline.

## Required Execution Flow

RuntimeMode
-> PolicyEngine
-> ExecutionAuthority
-> ConstitutionalDispatchPipeline
-> Executor
-> Replay Engine
-> Runtime Observation
-> Replay Persistence

## Forbidden Runtime Conditions

- direct executor invocation without governance
- replay-unsafe execution inside deterministic replay mode
- destructive side effects during replay-certified execution
- execution without replay trace continuity
- execution without observability emission

## Runtime Guarantee Direction

The runtime is evolving toward:

- mandatory governance
- replay-certifiable execution
- operational continuity
- constitutional runtime enforcement
