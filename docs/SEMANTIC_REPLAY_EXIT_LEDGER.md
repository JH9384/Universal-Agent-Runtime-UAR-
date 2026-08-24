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
| Semantic-distance distributions over real history | OPEN | `semantic_real_history_review.py` enforces observed-operational provenance, sanitization review, calibration/untouched-holdout separation, unique run and pair IDs, raw/preshadowed event authority, minimum cohort sizes, trace integrity, marginal thresholds, coupled per-case outcomes, telemetry-loss limits, and `PASS/HOLD/FAIL` verdicts. A trusted Ed25519 attestation now binds the source snapshot/window, code revision, review policy, complete run census, pairing/split/cohort/strata, and event/projection digests. Probability experiments and unsigned or tampered corpora are ineligible. | Supply the signed sanitized operational corpus and execute the untouched holdout |
| Deterministic projected shadow equality | PASS | Seven real `Executor` scenarios cover sequential, DAG/parallel, retry, rejection, timeout, cancellation, and annotated MCP tool/defer/conflict paths. Same-stream projection is exact, and two independently executed clean-state runs produce identical normalized projection hashes. Normalization removes only timestamps, UOR envelope fields, and timing metrics; a non-envelope result mutation is detected. | Retain the independent-pair and drift-negative tests as permanent gates |
| Runtime invocation identity | PASS | Stable invocation IDs join start/retry/terminal lifecycle events; reversed completion of repeated skill names is reconstructed correctly. Mixed/duplicate/orphan identity streams fail closed, and duplicate names in one skill-keyed parallel wave are explicitly rejected. | Retain identity and obstruction dual tests |
| Concurrent/stochastic overhead envelope | PASS | Latest seed `8191` rerun: 800 paired runs across greedy-wide and DAG-diamond workloads at concurrency 1/4/16/32. Zero projection/result/integrity drift; worst p95 ratio 1.0016, p99 ratio 1.0283, throughput retention 0.9970, order JSD 0.0017 bits, and order TV 0.0250. | Retain the 100-sample-per-stratum confirmatory workflow gate |
| Independent certificate verification | PASS | A real `Executor` decision carries an Ed25519 certificate reference. A public-key-only verifier requires an Ed25519 key and binds signature authenticity to the constraint, reason, evidence, commitment, causal stage context, final result, and full semantic-trace hash. Tampered-claim, causal-context, and wrong-key/algorithm controls are rejected. | Retain the signed certificate workflow gate and negative controls |
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
- raw and preshadowed evidence now fails closed on incomplete lifecycle grammar,
  orphan terminal events, malformed semantic annotations, non-object events,
  forged/duplicated semantic derivations, and sequential output reordering;
- the focused lifecycle/conformance/runtime-shadow slice passed 150/150 across
  random seeds `1`, `2`, `3`, `7`, and `42`.
- the frozen concurrent confirmatory gate passed all eight strata on seed
  `8191`; observer cost is paired on each candidate run, while independent
  executions measure result, scheduler-order, and semantic distributions.
- the Ed25519 decision-certificate campaign verifies one real `Executor`
  decision with public key material only and rejects tampered-claim and
  wrong-key duals.
- the Semantic Replay workflow now lints its complete implementation, script,
  and test surface. PR-attributable `E/W/F` findings are zero; the repository
  remains at the same 136 baseline findings as `main`.

## Next evidence tranche

1. Export a sanitized operational corpus using
   `uar.semantic-history-corpus.v1`, preserving the pre-declared calibration
   and untouched-holdout split, source window, code revision, and stable case
   coupling.
2. Run `scripts/semantic_history_prepare.py` to freeze the policy and sign the
   generated census manifest with the designated Ed25519 attestor.
   The reviewer must receive the public key through a separate trusted channel.
3. Run `scripts/semantic_real_history_review.py` with the trusted key ID and
   public-key path. Retain only the aggregate report; do not publish raw events.
4. Obtain an external review of the frozen semantic model, observer, and gate
   evidence before the merge/no-merge decision.

The current evidence inventory contains canonical fixtures, API audit entries,
and generated probability/decision experiments. Those artifacts strengthen
adversarial strata, but none carries the observed-operational provenance and
sanitized UAR `RunRecord` event history required to close the real-history row.
