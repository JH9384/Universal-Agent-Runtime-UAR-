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
| Scheduler diamonds and evaluation strategies | PASS | flat/non-flat local diamonds plus real greedy-wide and DAG-diamond `Executor` shadow pairs at concurrency 1/4/16/32; parallel branches join through the full causal frontier | Retain both scheduler shapes in the confirmatory gate |
| At least 10,000 result-equivalent semantic mutations | PASS | 14,000-case campaign with result-equivalent semantic families | None for synthetic gate |
| Observation-loss injection and measured indeterminacy | PASS | identical and divergent latent-pair campaign | Real telemetry-loss rate remains open |
| Semantic-distance distributions over real history | OPEN | `semantic_real_history_review.py` now enforces observed-operational provenance, a recorded sanitization review, calibration/untouched-holdout separation, unique run IDs, minimum cohort sizes, trace integrity, distribution thresholds, and measured telemetry-loss limits. Probability experiments are explicitly ineligible to close this row. | Supply the sanitized operational corpus and execute the untouched holdout |
| Deterministic projected shadow equality | PASS | Seven real `Executor` scenarios cover sequential, DAG/parallel, retry, rejection, timeout, cancellation, and annotated MCP tool/defer/conflict paths. Same-stream projection is exact, and two independently executed clean-state runs produce identical normalized projection hashes. Normalization removes only timestamps, UOR envelope fields, and timing metrics; a non-envelope result mutation is detected. | Retain the independent-pair and drift-negative tests as permanent gates |
| Concurrent/stochastic overhead envelope | PASS | Seed `8191`: 800 paired runs across greedy-wide and DAG-diamond workloads at concurrency 1/4/16/32. Zero projection/result/integrity drift; worst p95 ratio 1.0096, p99 ratio 1.0046, throughput retention 0.9971, order JSD 0.0024 bits, and order TV 0.0167. | Retain the 100-sample-per-stratum confirmatory workflow gate |
| Independent certificate verification | PASS | A real `Executor` decision carries an Ed25519 certificate reference. A public-key-only verifier checks both signature authenticity and exact semantic attachment; tampered-claim and wrong-key controls are rejected. | Retain the signed certificate workflow gate and both negative controls |
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
- SQLite `flush()` now uses a synchronous FIFO checkpoint barrier, so a
  dequeued-but-in-flight write cannot be mistaken for a completed write;
- UOR sandbox execution uses `spawn`, avoiding multithreaded `fork` deadlocks;
- the module-level UOR auth override was removed and its fixture now restores
  prior shared-app state;
- non-retryable exceptions now terminate after one `skill_failed` event rather
  than silently repeating failures without `skill_retry` transitions;
- cancellations now emit a schema-valid `skill_cancelled` runtime event and
  project to a semantic `REJECT` with reason `runtime_cancelled`;
- the focused lifecycle/conformance/runtime-shadow slice passed 150/150 across
  random seeds `1`, `2`, `3`, `7`, and `42`.
- the frozen concurrent confirmatory gate passed all eight strata on seed
  `8191`; observer cost is paired on each candidate run, while independent
  executions measure result, scheduler-order, and semantic distributions.
- the Ed25519 decision-certificate campaign verifies one real `Executor`
  decision with public key material only and rejects tampered-claim and
  wrong-key duals.

## Next evidence tranche

1. Export a sanitized operational corpus using
   `uar.semantic-history-corpus.v1`, preserving the pre-declared calibration
   and untouched-holdout split.
2. Run `scripts/semantic_real_history_review.py` on that corpus and retain only
   the aggregate report; do not publish raw operational events.
3. Obtain an external review of the frozen semantic model, observer, and gate
   evidence before the merge/no-merge decision.

The current evidence inventory contains canonical fixtures, API audit entries,
and generated probability/decision experiments. Those artifacts strengthen
adversarial strata, but none carries the observed-operational provenance and
sanitized UAR `RunRecord` event history required to close the real-history row.
