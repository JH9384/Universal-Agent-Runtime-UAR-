# Ω-7B.S Semantic Replay Validation

Status: Shadow-mode validation proposal  
Execution impact: None intended; non-interference is a validation requirement  
Production scoring impact: None

## Purpose

UAR replay answers whether a recorded run can be reconstructed faithfully.
Semantic Replay adds an orthogonal question:

> Did two executions preserve the same observable computational semantics even
> when they produced the same final result?

This layer does **not** record hidden chain-of-thought. It operates only on
machine-observable decision artifacts: candidate generation, admissibility,
constraints/certificates, evidence relations, commitments, observation
completeness, and declared causal dependencies.

## Semantic object

The minimum validation object is:

```text
S = (P, Γ, Q, Ω, E, K, M)
```

- `P`: causal partial order / stage-dependency relation.
- `Γ`: generated candidate set.
- `Q`: four-valued admissibility relation.
- `Ω`: obstruction / constraint / certificate relation.
- `E`: evidence relation attached to stage and candidate.
- `K`: commitment relation.
- `M`: observation mask for generated-but-unobserved candidate decisions.

A runtime sequence is one linearization of this causal structure; wall-clock
order is not itself semantic order.

## Execution grammar

```text
Generate -> Partition -> Evidence -> Commit -> Replay
   Γ       (A,R,D,C)       η         K        R
```

The four runtime admissibility states are:

- `ADMIT` — support exists and no obstruction is currently established.
- `REJECT` — obstruction exists and no support sufficient to override it exists.
- `DEFER` — the runtime explicitly judged that available evidence is insufficient.
- `CONFLICT` — support and obstruction coexist.

A useful support/obstruction encoding is:

```text
DEFER    = (0,0)
ADMIT    = (1,0)
REJECT   = (0,1)
CONFLICT = (1,1)
```

Dualization swaps support and obstruction, so ADMIT and REJECT are dual while
DEFER and CONFLICT are self-dual.

`UNOBSERVED` is deliberately **not** a fifth runtime decision state. It belongs
to the certifier's observation mask `M` and means the semantic decision event was
not observed. Therefore `DEFER != UNOBSERVED`.

## Stage conservation / integrity invariants

For a well-formed stage:

```text
Γ = A ⊔ R ⊔ D ⊔ C ⊔ M
```

where the classes are pairwise disjoint and:

```text
M = Γ - dom(Q)
```

A fully observed stage has `M = ∅`.

Additional invariants:

- every decision candidate must have been generated,
- duplicate candidate decisions are invalid,
- commitments must refer to generated candidates,
- dependency references must resolve,
- self-dependencies and causal cycles are invalid.

`validate_semantic_trace()` reports these defects explicitly.

## Causal semantics and finality

Finality is derived causally, not from tuple position. Explicit `terminal=True`
stages take precedence. Otherwise the terminal stage set is the sink set of the
dependency DAG.

The causal relation is compared using its transitive closure so redundant raw
edge spelling does not create semantic drift.

For `n` independent stages, valid partial executions form the Boolean lattice
`2^n`; its Hasse diagram is the hypercube `Q_n`. This is used only as validation
geometry for scheduler independence, not as production semantics.

For two independent enabled stages `a` and `b`, the local scheduler diamond is:

```text
I -> I+a -> I+a+b
I -> I+b -> I+a+b
```

and the semantic defect is conceptually:

```text
χ_ab(I) = d_sem(T_b T_a(S_I), T_a T_b(S_I))
```

A flat diamond has `χ_ab=0`. Under finite termination and appropriate local
confluence assumptions, local diamond checks are the route toward global
scheduler semantic equivalence.

## Relational evidence and obstruction

Evidence meaning depends on attachment, not inventory. Therefore comparison
uses relations of the form:

```text
E ⊆ Stage × Candidate × Evidence
```

rather than only a global set of evidence IDs.

Obstruction likewise preserves attachment:

```text
Ω ⊆ Stage × Candidate × State × Constraint × Certificate/Reason
```

This detects evidence swaps or obstruction reassignment even when the global
ID inventory is unchanged.

## Vector-valued comparison

Semantic comparison remains vector-valued and is not collapsed into a Trust
Spine score:

```text
D(A,B) = (d_R, d_S, d_O, d_F, d_E, d_P)
```

- `d_R`: final-result divergence.
- `d_S`: causal-terminal survivor divergence.
- `d_O`: relational obstruction divergence.
- `d_F`: stagewise semantic-filtration divergence.
- `d_E`: relational evidence/certificate divergence.
- `d_P`: causal-partial-order divergence.

The implementation also reports maximum local filtration divergence, not only
the mean, so a single severe local defect is not hidden by averaging.

These are divergence measures. They are not probabilities and are not yet Trust
Spine weights.

## Identity coherence

The comparator must never report both:

```text
D(A,B) == 0
```

and a non-null semantic divergence. Constraint/reason changes are therefore part
of stage semantics; evidence attachment is part of `d_E`; causal changes are
part of `d_P`.

Canonical semantic serialization is exposed through `semantic_trace_hash()`.
The hash is stage-order invariant when causal-relational semantics are unchanged.

## Divergence families

The expanded observable divergence vocabulary is:

| Code | Meaning |
| --- | --- |
| `G-` | Generation divergence |
| `A-` | Admissibility / constraint / reason divergence |
| `E-` | Evidence or certificate attachment divergence |
| `K-` | Commitment divergence |
| `P-` | Causal/dependency or terminal-semantics divergence |
| `O-` | Observation-domain divergence / missing semantic telemetry |

In a DAG there may be multiple causally minimal earliest divergences. The report
preserves a minimal-divergence set and retains one deterministic
`first_divergence` value for compatibility.

## Comparison outcome

The certifier reports:

```text
EQUIVALENT | DIFFERENT | INDETERMINATE
```

`INDETERMINATE` is required when incomplete observation prevents a defensible
same/different judgment. It is not a runtime DEFER decision.

## Semantic Replay vs Semantic Verification

Semantic Replay compares what the runtime reported. It does not automatically
prove that a reported reason or certificate is true.

The validation layer therefore exposes a separate certificate-integrity check:

```text
Q_self = runtime-reported semantics
Q_ver  = independently verified certificate semantics
```

`verify_decision_certificates()` reports missing or invalid independent
certificate verification. Replay equivalence and semantic verification remain
separate assurance dimensions.

## Directed risk is not semantic distance

Semantic divergence can be symmetric while operational consequence is not.
For example, a policy may assign much higher consequence to `REJECT -> ADMIT`
than to `ADMIT -> REJECT`.

The module therefore keeps directional risk policy external to semantic
distance. `directed_transition_risk()` accepts a caller-supplied risk matrix.

## Shadow-mode non-interference

For deterministic execution, let `π` erase shadow semantic events. The strong
non-interference target is:

```text
π(runtime_shadow) = runtime_baseline
```

not merely equal final output. `project_nonsemantic_events()` provides the
projection primitive.

For concurrent or stochastic execution, exact path equality may be inappropriate;
validation should compare output, scheduler, latency, and semantic-trace
distributions and establish an explicit overhead envelope before production use.

No semantic trace result may alter planning, scheduling, tool execution, trust
ranking, certification level, or committed outcome during Ω-7B.S.

The existing Trust Spine weights remain unchanged.

## Stratified mutation campaign

`scripts/semantic_replay_validation.py` now stratifies the campaign across:

```text
G    generation mutation
A    admissibility mutation
E    evidence mutation
K    commitment mutation
P    causal/dependency mutation
O    observation-loss mutation
NULL semantic-null representation change
```

The default campaign is:

```bash
python scripts/semantic_replay_validation.py --iterations 14000 --seed 2049
```

This gives approximately equal sampling per family. `2049` is only a
reproducibility seed and has no production/theoretical meaning.

Expected outcomes are family-specific:

- `G/A/E/K/P` -> `DIFFERENT` while preserving the final result in the seeded cases,
- `O` -> `INDETERMINATE`,
- `NULL` -> `EQUIVALENT`.

Report detection/localization per family. A 100% aggregate result must not be
interpreted as universal proof outside the sampled mutation distribution.

`scripts/semantic_replay_stochastic_review.py` provides an additional compact
cross-check of the same stratified contract.

## Statistical interpretation

Zero misses in `n` IID trials supports a bound on the sampled mutation law; it
is not proof over all possible traces. Rare-event validation should therefore
combine:

- stratified random sampling,
- adversarial/metamorphic cases,
- semantic-null controls,
- scheduler diamond tests,
- observation-loss injection,
- dual observation oracles: no false `DIFFERENT` for identical latent runs and
  no false `EQUIVALENT` for divergent latent runs,
- real historical replay distributions.

Future stochastic validation may compare semantic trace distributions using
appropriate distributional measures (for example JS divergence, Wasserstein,
MMD, or permutation/bootstrap procedures), but no such quantity is currently a
Trust Spine weight.

### Real-history evidence planes

`scripts/semantic_real_history_review.py` prevents experimental probability
artifacts from being mistaken for operational replay evidence. Its input uses
`uar.semantic-history-corpus.v1` and declares:

- `provenance.source_kind = observed_operational`;
- `provenance.model_generated = false`;
- a completed sanitization record with method, reviewer, and source snapshot;
- unique run IDs;
- a stable `pair_id` binding the corresponding baseline and candidate case;
- an explicit `event_mode` of `raw_runtime` or `preshadowed`;
- for preshadowed streams, a committed runtime-projection hash that must match
  semantic-event erasure;
- a pre-declared `calibration` or `holdout` split for every run;
- `baseline` or `candidate` cohort, task class, final-result class, and runtime
  events for every run.

The calibration split can inform investigation. Only the untouched holdout can
close the release gate. By default, every holdout stratum requires at least 20
runs per cohort, JS divergence no greater than 0.02 bits, total variation no
greater than 0.05, telemetry loss no greater than 1% in either cohort, and a
cohort telemetry-loss difference no greater than 0.5 percentage points.

Telemetry loss is measured from `M = Γ - dom(Q)` after the shadow observer has
projected stored runtime events into the frozen semantic object. A corpus with
no holdout, duplicate IDs, invalid traces, incomplete provenance, synthetic
origin, or model-generated origin is reportable as probability-plane evidence
but is not release-gate eligible.

Marginal equality is not sufficient. If `κ` is the declared case coupling, the
reviewer also evaluates each `(baseline, candidate)` pair. A corpus may have
identical trace-hash marginals while every paired case changes semantics; such
semantic reassignment fails the coupled gate even when JS divergence and total
variation are both zero.

The history verdict is three-valued:

- `PASS`: all required evidence and holdout limits are verified;
- `FAIL`: a witnessed integrity defect, semantic difference, or limit violation
  exists;
- `HOLD`: required evidence is absent, unverifiable, or underpowered.

Example:

```bash
python scripts/semantic_real_history_review.py sanitized-history.json \
  --output semantic-real-history-report.json
```

The aggregate report is suitable for retention. Raw operational history is not
required in the repository or CI artifact.

A useful future statistic is conditional process drift:

```text
I(version ; semantic_trace | final_result, task_class)
```

which asks whether process semantics reveal the running version even after
controlling for the fact that the final answer stayed the same.

## Equivalence, correctness, and generation completeness

These are separate questions:

```text
E: are two executions semantically equivalent?
C: did an execution satisfy the task/specification?
G: was the generated candidate space adequate?
```

Semantic Replay can establish `E` under its observation assumptions. It does
not by itself prove `C` or `G`. Two versions can be perfectly equivalent while
reproducing the same incomplete or incorrect behavior.

## Validation exit gate

The Ω-7B.S gate now requires:

- trace integrity/conservation invariants,
- no zero-distance / non-null-divergence contradiction,
- causal rather than positional finality,
- relational evidence and obstruction comparison,
- causal/dependency comparison,
- explicit `UNOBSERVED` accounting and `INDETERMINATE` outcome,
- stable canonical semantic hashing,
- 100% expected outcome/localization on the stratified seeded corpus,
- 0 false positives on semantic-null controls,
- local scheduler-diamond tests and sequential/greedy/DAG evaluation,
- result-equivalent mutation corpus >= 10,000 cases,
- observation-loss injection tests,
- bidirectional observation-loss assertions against false `DIFFERENT` and false
  `EQUIVALENT` verdicts,
- semantic-distance distributions over real replay history,
- deterministic shadow projection equality where applicable,
- measured stochastic/concurrent shadow overhead and distributional impact,
- no Trust Spine weighting change until empirical validation exists.

## Contributor review

The Maxwell + Jolly Crue consensus and each contributor's distinct deliverable
are captured in `docs/MAXWELL_JOLLY_CRUE_REVIEW.md`.

## Deliberate exclusions

The following experimental constructs remain outside UAR production semantics:

- Nikola Hypercube geometry as a production architecture,
- 2049/2304 addressing conventions,
- matrix payload assumptions,
- hidden/free-form reasoning traces.

The reusable production candidate is the observable causal-admissibility-
evidence-commitment protocol and its comparison/verification algebra.
