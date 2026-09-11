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

## Evidence graph

`uar.objects.evidence_graph` exposes a read-only graph projection over canonical UAR objects and their explicit links. It is intentionally derived state: the graph can be discarded and rebuilt from the immutable object store.

The projection follows this rule:

`execution/object -> evidence -> witness/object links`

Missing linked witnesses are surfaced as unresolved nodes rather than silently dropped. This is important for assurance: absence of evidence remains observable.

`mission_control_evidence_projection()` provides an operator-facing evidence summary grouped by control and observed result. It deliberately returns:

`assessment_status = not-assessed`

because Mission Control may display evidence but may not self-certify a control.

## Architectural separation

- Runtime execution creates effects and execution records.
- Evidence emission describes those observed facts.
- Evidence graph projections make facts navigable.
- Assessment evaluates whether facts satisfy a requirement.
- Governance accepts risk or directs remediation.

This keeps execution authority, assessment authority, and governance authority distinct.

## Duality

- execution ↔ assessment
- control ↔ evidence
- authority ↔ accountability
- effect ↔ witness
- assertion ↔ verification
- canonical history ↔ disposable projection

## Baseline 0.4 gate

This emitter and graph are necessary but not sufficient for promotion. Baseline 0.4 still requires:

1. authoritative external control relationship import;
2. schema-valid OSCAL artifacts;
3. Mission Control consuming evidence objects rather than implementation assertions;
4. an end-to-end sovereign recovery trial;
5. external policy-engine execution;
6. independent implementation/conformance evidence.
