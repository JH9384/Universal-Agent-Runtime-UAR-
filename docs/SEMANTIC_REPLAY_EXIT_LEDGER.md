# Ω-7B.S Semantic Replay Exit Ledger

Status values:

- `PASS` — implementation, focused test, and executed validation evidence exist.
- `PARTIAL` — mechanism exists, but release-grade empirical evidence is incomplete.
- `OPEN` — required evidence has not been produced.
- `HOLD` — intentionally prohibited until the empirical gate closes.

This ledger separates comparator correctness from runtime non-interference. A
green synthetic campaign does not close a real-runtime or stochastic criterion.

| Exit criterion | Status | Implementation / test evidence | Remaining evidence |
| --- | --- | --- | --- |
| Stage conservation and trace integrity | PASS | `validate_semantic_trace()`; consensus integrity tests | None for shadow validation scope |
| No zero-distance/non-null-divergence contradiction | PASS | identity-coherence tests in `tests/test_semantic_trace_consensus.py` | None |
| Causal rather than positional finality | PASS | causal terminal derivation and consensus tests | None |
| Relational evidence reassignment detection | PASS | relational evidence comparator and consensus regression | None |
| Relational obstruction attachment | PASS | candidate/constraint/certificate relation comparison | None |
| Dependency changes classified as `P-` | PASS | causal signature comparison and causal mutation family | None |
| Missing telemetry classified as `O-` / `INDETERMINATE` | PASS | bidirectional observation-loss campaign | None for sampled observation law |
| Stable canonical semantic hash | PASS | `semantic_trace_hash()` and canonicalization tests | Cross-version fixture should be retained |
| Stratified `G/A/E/K/P/O/NULL` mutation campaign | PASS | 14,000-case seeded workflow campaign | Continue reporting per family |
| Expected outcome and localization accuracy | PASS | 100% per family on seeded corpus | Claim remains limited to sampled corpus |
| Semantic-null false-positive control | PASS | `NULL` family: zero false positives | Continue as permanent regression gate |
| Scheduler diamonds and evaluation strategies | PARTIAL | flat/non-flat local diamond tests and minimal antichain tests | Real sequential/greedy/DAG paired executions |
| At least 10,000 result-equivalent semantic mutations | PASS | 14,000-case campaign with result-equivalent semantic families | None for synthetic gate |
| Observation-loss injection and measured indeterminacy | PASS | identical and divergent latent-pair campaign | Real telemetry-loss rate remains open |
| Semantic-distance distributions over real history | OPEN | distributional review harness exists | Populate and execute real replay corpus |
| Deterministic projected shadow equality | PARTIAL | `pair_runtime_with_shadow()` wraps a real `Executor` stream; success and rejection regressions require exact baseline recovery after semantic-event erasure | Expand beyond the first deterministic runtime pair into the declared representative corpus |
| Concurrent/stochastic overhead envelope | OPEN | semantic/latency statistics module exists | Predeclare thresholds and measure real runs |
| Independent certificate verification | PARTIAL | verifier hook and separation from replay verdict | Exercise a real certificate family |
| No Trust Spine weighting change | HOLD | PR introduces no weighting changes | Remain on hold until empirical validation closes |

## Runtime preconditions

These are not semantic comparator laws, but they must be green before runtime
non-interference evidence is trustworthy:

- shared executor shutdown/reinitialization must not poison later workloads;
- SQLite writer startup and shutdown must be synchronous and observable;
- no unhandled background-thread exceptions or pending-task destruction;
- conformance executions must not time out because of leaked runtime state;
- baseline repository failures must be distinguished from PR-attributable
  regressions.

Current lifecycle evidence:

- the shared batch-pool replacement no longer restores a closed executor;
- SQLite writer construction now waits for observable startup and closure;
- UOR sandbox execution uses `spawn`, avoiding multithreaded `fork` deadlocks;
- the module-level UOR auth override was removed and its fixture now restores
  prior shared-app state;
- the focused lifecycle/conformance/runtime-shadow slice passed 110/110 across
  random seeds `1`, `2`, `3`, `7`, and `42`.

## Next evidence tranche

1. Re-run the full ordering-stress workflow after the sandbox/auth repairs.
2. Expand the paired real-runtime corpus beyond the first deterministic
   `Executor` pair, stratified by deterministic, DAG,
   tool-use, rejection, defer, conflict, retry, cancellation, timeout, and
   concurrent execution paths.
3. Require exact projected-event equality for deterministic pairs.
4. Predeclare and measure latency, scheduler, result, and semantic-trace
   distribution thresholds for stochastic/concurrent pairs.
5. Exercise at least one independently verifiable certificate family.
