# Ω-7B.S Semantic Replay Validation

Status: Shadow-mode validation proposal  
Execution impact: None  
Production scoring impact: None

## Purpose

UAR replay currently answers whether a recorded run can be reconstructed
faithfully. Semantic Replay adds an orthogonal question:

> Did two executions preserve the same observable decision structure even when
> they produced the same final result?

This layer does **not** record hidden chain-of-thought. It operates only on
machine-observable decision artifacts: candidate generation, admissibility
states, evidence/certificate references, commitments, and declared semantic
dependencies.

## Execution grammar

The validation model uses the following portable execution grammar:

```text
Generate -> Partition -> Evidence -> Commit -> Replay
   Γ       (S,O,U,C)       η         κ        R
```

The four admissibility states are:

- `ADMIT` — candidate is presently executable/admissible.
- `REJECT` — an explicit obstruction/constraint excludes the candidate.
- `DEFER` — admissibility cannot yet be established from available evidence.
- `CONFLICT` — support and obstruction coexist and require resolution/policy.

## Semantic trace

Each stage is represented as:

```text
D_t = (Γ_t, S_t, O_t, U_t, C_t, E_t, κ_t)
```

A run is a semantic trace:

```text
T(R) = (D_0, D_1, ..., D_n)
```

Stable `stage_id` values are used to compare semantic stages independently of
wall-clock completion order. `dependencies` carry declared causal structure,
allowing sequential, greedy, and DAG schedulers to converge on the same
semantic trace when only independent execution order changes.

## Vector-valued comparison

Semantic comparison intentionally does not collapse immediately to one trust
score. The first implementation reports:

```text
D(A,B) = (d_R, d_S, d_O, d_F, d_E)
```

Where:

- `d_R`: final result distance.
- `d_S`: final admitted/survivor-set distance.
- `d_O`: accumulated rejected/obstructed-set distance.
- `d_F`: stagewise filtration / decision-topology distance.
- `d_E`: evidence and certificate basis distance.

A later validation phase may add counterfactual distance `d_CF` after a
controlled perturbation corpus exists.

## First semantic divergence

The certifier locates the earliest observable semantic divergence and classifies
it into one of four failure families:

| Code | Meaning |
| --- | --- |
| `G-` | Generation divergence: candidate/stage exists on only one side |
| `A-` | Admissibility divergence: ADMIT/REJECT/DEFER/CONFLICT differs |
| `E-` | Evidence divergence: evidence/certificate basis differs |
| `K-` | Commitment divergence: selected outcome differs |

This lets UAR distinguish, for example, a planner that failed to consider the
right action from one that considered it and rejected it incorrectly.

## Semantic equivalence ladder

The initial validation ladder is:

| Level | Requirement | Meaning |
| --- | --- | --- |
| S0 | Result | Same committed outcome |
| S1 | Survivor | Same final admitted candidate set |
| S2 | Obstruction | Same candidates ultimately rejected |
| S3 | Filtration | Same stagewise decision topology |
| S4 | Evidence | Equivalent observable evidence/certificate basis |
| S5 | Counterfactual | Equivalent under approved perturbations (future) |
| S6 | Behavioral | Equivalent admissible future behavior (future) |

S0 is deliberately weak. A build may be S0-equivalent while materially
changing how it eliminates alternatives.

## Shadow-mode invariants

Semantic Replay must remain observational during Ω-7B.S validation:

```text
κ_shadow = κ_baseline
```

No semantic trace result may alter planning, scheduling, tool execution, trust
ranking, or certification level during the validation tranche.

The existing runtime certification weights remain unchanged.

## Mutation campaign

`scripts/semantic_replay_validation.py` seeds result-equivalent semantic
mutations and harmless representational reorderings. The default campaign is:

```bash
python scripts/semantic_replay_validation.py --iterations 10000 --seed 2049
```

`2049` is used only as a reproducibility seed and carries no production or
theoretical meaning.

The campaign requires:

1. All seeded result-equivalent semantic mutations are detected.
2. Every mutation receives a first-divergence class (`G-`, `A-`, `E-`, `K-`).
3. Stable-stage-id reorderings produce zero filtration false positives.

## Validation exit gate

The proposed Ω-7B.S exit gate is:

- 100% detection of seeded causal semantic mutations.
- 100% first-divergence localization on the seeded corpus.
- 0 false positives on declared representation-equivalent reorderings.
- Stable semantic serialization/hash in a subsequent patch.
- Cross-scheduler equivalence checks for sequential / greedy / DAG runs.
- Result-equivalent mutation corpus >= 10,000 cases.
- Distribution of semantic distance measured over real replay history.
- No execution outcome change with shadow mode enabled.

## Deliberate exclusions

The following experimental constructs are **not** part of UAR production
semantics:

- Nikola Hypercube geometry.
- 2049/2304 addressing conventions.
- Matrix payload assumptions.
- Hidden/free-form reasoning traces.

Those were useful experimental scaffolds. The production candidate is the
observable semantic execution protocol and its comparison algebra.
