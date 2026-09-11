# PSERA Evidence Emitter — E&E-03

## Purpose

UAR already produces immutable objects, execution records, lineage, canonical digests, and SQLite-backed persistence. The PSERA Evidence Emitter extends that existing substrate; it does not create a second audit database.

## Architectural rule

**Execution produces facts. Assessment produces judgments.**

The emitter may record observed status, decision, authority path, policy version, external effect, witnesses, limitations, and framework references. It must not mark a control `passed`, `satisfied`, `compliant`, or `certified`.

## Evidence contract

Each evidence record is an immutable UAR object with media type:

`application/vnd.psera.evidence+json`

and schema identifier:

`psera.evidence.contract.v0.1`

The content carries:

- `control_id`
- `claim`
- `subject`
- `source`
- `assessment_method`
- `result`
- `authenticity_status`
- `authority_path`
- `policy_version`
- `decision`
- `effect`
- `limitations`
- `owner`
- `framework_refs`

Witnesses are linked by digest using `rel=witness`.

## Duality

- execution ↔ assessment
- control ↔ evidence
- authority ↔ accountability
- effect ↔ witness
- assertion ↔ verification

## Baseline 0.4 gate

This emitter is necessary but not sufficient for promotion. Baseline 0.4 still requires:

1. authoritative external control relationship import;
2. schema-valid OSCAL artifacts;
3. Mission Control consuming evidence objects rather than implementation assertions;
4. an end-to-end sovereign recovery trial;
5. external policy-engine execution;
6. independent implementation/conformance evidence.
