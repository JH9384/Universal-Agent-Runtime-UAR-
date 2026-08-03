# FCRL v4 — UAR Evidence Pack Validation

## Purpose

Freeze the current FCRL certificate calculus and test whether it provides measurable operational value in the UAR Evidence Pack v2 workflow.

This phase does **not** add a new evidence store, mutate trust, change recurrence, alter certification, or replace the existing evidence-pack composer. It introduces a read-only comparative measurement seam.

## Frozen hypothesis

A property-indexed certificate layer is useful only when it improves at least one operationally meaningful outcome beyond ordinary validation:

- prevents false evidence collapse;
- preserves lineage or replay links that would otherwise be lost;
- rejects invalid exact or approximate compositions earlier;
- reduces recurrence, trust, ranking, or certification disagreement relative to a declared reference;
- produces reusable evidence for later operator decisions;
- justifies its runtime, storage, and authoring overhead.

The phase must be allowed to falsify the hypothesis.

## Trial arms

Each trial declares one reference and three candidate arms:

1. `reference_exhaustive` — manually audited or exhaustive expected output;
2. `current` — current production behavior;
3. `ordinary_validation` — conventional schema, invariant, and application validation;
4. `certificate` — the same workflow with explicit source property, environment, exact/approximate adequacy, quantitative grade, and policy admission.

The comparator does not assume that the certificate arm is superior.

## Retained discrepancy vector

For each candidate, `compare_evidence_packs` retains:

- missing and extra sections;
- section-availability disagreement;
- status and correlation-status disagreement;
- path-specific missing and extra evidence references;
- path-specific missing and extra run references;
- aggregate recurrence-count error;
- aggregate trust-score error.

The full vector is primary evidence. A scalar distance is secondary and must publish its weights.

Default distance:

```text
1 * section differences
+ 2 * availability mismatches
+ 2 * status mismatches
+ 4 * evidence-reference differences
+ 3 * run-reference differences
+ 1 * recurrence absolute error
+ 1 * trust-score absolute error
```

The stronger default penalties on evidence and run references reflect the operational importance of lineage and replay. They are a declared policy, not a theorem or universal weighting.

Reference comparison uses path-specific occurrence counts. A reference lost from one semantic relationship cannot be hidden merely because the same identifier occurs elsewhere in the pack.

## Validation disciplines

### Ordinary application validation

`audit_evidence_pack_ordinary` checks:

- Evidence Pack v2 version;
- required section presence;
- duplicate section names;
- section-name and availability types;
- declared trust-score range.

### Certificate semantic validation

`audit_evidence_pack_certificate` includes the ordinary obligations and adds cross-field checks:

- correlation availability agrees with retained correlation evidence;
- recurrence counts agree with retained later-run references;
- recurrence status agrees with later-run references;
- every correlation run retains its evidence reference;
- incident affected runs retain lineage;
- available replay retains its run evidence;
- duplicate evidence and run references are obstructed.

These are application-level certificate obligations. They are not claimed to be a complete universal semantics of evidence.

## Overhead fields

Each arm may additionally record:

- runtime in milliseconds;
- serialized or retained storage in bytes;
- notes about human authoring or reviewer effort.

Semantic improvement alone does not establish practical superiority.

## Initial adversarial families

### False collapse

Two records are similar but lack a valid equivalence witness. An implementation that collapses them loses one evidence or run reference.

Expected certificate behavior: retain or mark unresolved.

### Missed recurrence

A later recurrence run is omitted from a correlation or incident section.

Expected measurement: missing run reference and recurrence-count disagreement.

### Exact/approximate adequacy split

The reference path satisfies a downstream assumption while the practical approximate path does not.

Expected certificate behavior: composition unavailable until the approximate obligation is discharged.

### Trust drift

A duplicated, lost, or misclassified recommendation changes a trust score.

Expected measurement: nonzero trust-score absolute error and any associated status disagreement.

### Missing section masked as nominal

A correlation section is absent or unavailable but a consumer treats the evidence pack as complete.

Expected measurement: missing section or availability disagreement rather than silent nominal classification.

## Falsification criteria

Substantially revise or reject the certificate layer for this workflow when repeated trials show any of the following:

- it catches no defects beyond ordinary validation;
- its adequacy witnesses are mostly boilerplate with no decision effect;
- its grades never affect policy admission;
- it requires ad hoc extensions for ordinary UAR failure semantics;
- its runtime, storage, or authoring burden exceeds the replay and safety value;
- ordinary typed contracts produce the same evidence more clearly.

## Support criteria

The case study supports continued development when the certificate arm repeatedly and reproducibly:

- has lower declared discrepancy than ordinary validation;
- prevents at least one false collapse or lineage loss;
- rejects at least one invalid composition before downstream scoring;
- provides replayable explanations that are reused by more than one consumer;
- propagates uncertainty into an actual policy or certification decision.

## Current implementation

`uar.core.evidence_pack_validation` provides:

- `compare_evidence_packs`;
- `evaluate_validation_trial`;
- `classify_certificate_leverage`;
- `render_validation_report`.

`uar.core.evidence_pack_certificate` provides:

- `audit_evidence_pack_ordinary`;
- `audit_evidence_pack_certificate`;
- `compare_evidence_pack_audits`.

`uar.core.evidence_pack_validation_corpus` provides:

- corpus-document parsing;
- three-arm case evaluation;
- aggregate classification counts;
- certificate-only obstruction counts;
- structured and markdown reporting.

The command-line runner is `scripts/fcrl_v4_evidence_pack_corpus.py`.

The synthetic control corpus is `docs/research/fcrl_v4_seed_corpus.json`. The blinded historical procedure is `docs/research/FCRL_V4_HISTORICAL_CORPUS_PROTOCOL.md`.

All modules are read-only and are not wired into production APIs.

## Completion boundary

The implementation can establish:

- `instrument_complete`;
- `seed_control_complete`.

It cannot establish the historical or operational verdict without a real selected corpus and independently frozen references.

## Evidence boundary

The current tests establish that the measurement harness retains declared discrepancies, distinguishes synthetic current, ordinary-validation, and certificate arms, detects semantic lineage obligations beyond ordinary shape validation, and preserves no-benefit and negative-benefit controls.

They do not establish practical leverage on historical UAR runs. The next data gate remains a blinded historical corpus with manually adjudicated reference packs.
