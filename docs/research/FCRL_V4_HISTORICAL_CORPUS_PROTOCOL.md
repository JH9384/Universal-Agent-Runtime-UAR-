# FCRL v4 — Historical Evidence-Pack Corpus Protocol

## Objective

Measure whether certificate-mediated validation provides operational value beyond current behavior and ordinary application validation on historical UAR Evidence Pack v2 cases.

The protocol is designed to prevent the evaluator from tuning the certificate arm to the reference after seeing the answer.

## Evidence boundary

The repository contains a synthetic seed corpus at `docs/research/fcrl_v4_seed_corpus.json`. It validates the parser, comparator, certificate audit, reporting, and falsification controls. It is not historical evidence and must not be reported as operational leverage.

A historical result requires externally supplied or locally exported UAR records that are not currently present in this repository.

## Corpus unit

Each case contains:

- a stable opaque `case_id`;
- a provenance classification;
- one manually adjudicated reference pack;
- three candidate packs named exactly:
  - `current`;
  - `ordinary_validation`;
  - `certificate`;
- optional runtime, storage, and reviewer-effort notes.

The reference and candidates must use the JSON-compatible schema accepted by `corpus_cases_from_document`.

## Selection

Select cases before adjudication using documented criteria. The minimum first corpus is 30 cases distributed across:

- nominal packs;
- single failure signals;
- repeated failures;
- linked incidents;
- recommendation outcomes;
- trust movement;
- no-later-recurrence results;
- later-recurrence results;
- missing or partial source data;
- conflicting or duplicated lineage.

Do not select only cases already known to favor certificate validation.

## Blinding

1. A collector exports the source records and assigns opaque case identifiers.
2. An adjudicator constructs the reference pack without seeing which candidate came from which arm.
3. The three candidate packs are shuffled and stored under temporary labels.
4. The evaluator runs discrepancy and audit calculations.
5. Arm labels are revealed only after the reference and metric outputs are frozen.

Where one person performs multiple roles, record the loss of independence explicitly.

## Reference adjudication

The reference pack must be justified by source records rather than reconstructed from any candidate arm. Record:

- included and excluded runs;
- evidence-reference decisions;
- recurrence decisions;
- recommendation linkage;
- trust inputs;
- unresolved ambiguities;
- adjudicator identity or pseudonym;
- adjudication timestamp;
- a content digest of the frozen reference.

Unresolved evidence must remain unresolved. Absence of a distinction witness is not proof of equivalence.

## Validation disciplines

### Current

Run the unmodified Evidence Pack v2 path used by the selected historical revision.

### Ordinary validation

Apply conventional schema, type, range, required-section, and application-invariant checks without using the certificate-specific cross-field obligations.

### Certificate validation

Apply the same construction inputs together with the explicit semantic audit in `uar.core.evidence_pack_certificate`:

- recurrence count agrees with retained later-run references;
- recurrence status agrees with later-run evidence;
- every correlation run has an evidence reference;
- incident affected runs retain lineage;
- available replay retains its run evidence;
- duplicate evidence and run references are obstructed;
- required structural contracts remain satisfied.

The certificate arm must not repair a case using the adjudicated reference. It may reject the candidate as inadmissible or produce an independently constructed candidate.

## Primary outcomes

For every arm retain the complete discrepancy vector:

- section differences;
- availability differences;
- status differences;
- path-specific evidence-reference differences;
- path-specific run-reference differences;
- recurrence-count error;
- trust-score error.

Also retain:

- ordinary audit obstructions;
- certificate audit obstructions;
- certificate-only obstructions;
- runtime;
- storage;
- human authoring and review time;
- whether an obstruction changed an operator or certification decision.

The scalar semantic distance is secondary and uses declared weights.

## Support threshold

The first corpus supports further development only when all of the following hold:

1. The certificate arm has lower mean and median semantic distance than ordinary validation.
2. At least three cases contain certificate-only obstructions confirmed by adjudicators as operationally material.
3. At least one certificate obstruction prevents lineage loss, false recurrence, false collapse, or an invalid downstream decision.
4. The result is not driven by one case or one metric weight choice.
5. Runtime, storage, and human effort are reported rather than omitted.

These thresholds are protocol decisions, not mathematical theorems.

## Falsification threshold

Classify the UAR application as unsupported or not cost-effective when any of the following persists after adjudication corrections:

- no certificate-only material defect is found;
- certificate and ordinary validation tie on semantic outcomes;
- certificate validation performs worse;
- gains disappear under reasonable weight sensitivity analysis;
- witness construction is mostly boilerplate;
- operational overhead exceeds the observed safety or replay value;
- ordinary typed contracts express the same obligations more clearly.

## Execution

Run the seed control:

```bash
python scripts/fcrl_v4_evidence_pack_corpus.py \
  docs/research/fcrl_v4_seed_corpus.json \
  --json-out artifacts/fcrl_v4_seed_result.json \
  --markdown-out artifacts/fcrl_v4_seed_report.md
```

Run a blinded historical corpus by replacing the input path. Do not edit metric code after unblinding. Any post-unblinding correction requires a new corpus revision and a documented reason.

## Completion states

- `instrument_complete`: code, parser, audits, controls, and reporting pass.
- `seed_control_complete`: synthetic seed produces its declared control behavior.
- `historical_collection_complete`: selected source cases and frozen references exist.
- `blinded_evaluation_complete`: all arms are measured before label reveal.
- `operational_verdict_complete`: support or falsification threshold is applied.

The current repository work can reach the first two states without external historical data. The remaining states require a real corpus.
