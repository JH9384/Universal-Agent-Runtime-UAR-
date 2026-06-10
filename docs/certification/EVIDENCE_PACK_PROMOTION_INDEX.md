# Evidence Pack Promotion Index

## Status

This index tracks promoted Evidence Pack v2 artifacts that have been intentionally committed as certification evidence.

## Purpose

Generated evidence packs are ignored by default under `reports/evidence_pack/`. This index lists only promoted, reviewed, tracked evidence packs.

## Promotion Rules

Promoted artifacts must have:

1. a matching certification or operations document,
2. a clear validation or release purpose,
3. no secrets or sensitive values,
4. an explicit promotion commit,
5. an authoritative tag when applicable.

## Promoted Evidence Packs

| Lane | Run ID | Artifact Path | Authority Tag | Purpose |
| --- | --- | --- | --- | --- |
| D5M | `d5m-promotion-smoke` | `docs/certification/artifacts/d5m/d5m-promotion-smoke/` | `v1.2.32-d5m-final-artifact-authority` | Promotion smoke validating the D5L promotion template |

## D5M Artifacts

- `docs/certification/artifacts/d5m/d5m-promotion-smoke/d5m-promotion-smoke_evidence_pack.json`
- `docs/certification/artifacts/d5m/d5m-promotion-smoke/d5m-promotion-smoke_evidence_pack.md`

## Superseded D5M Tags

| Tag | Reason |
| --- | --- |
| `v1.2.28-d5m-evidence-promotion-smoke` | Created before artifacts were committed |
| `v1.2.29-d5m-evidence-promotion-validated` | Promotion doc committed, but artifact authority later clarified |
| `v1.2.30-d5m-promotion-authority` | Authority note before force-added artifacts were committed |
| `v1.2.31-d5m-promoted-artifacts-committed` | Artifacts committed; superseded by final authority note |

## Current D5M Authority

`v1.2.32-d5m-final-artifact-authority`

## Guardrails

- Do not list unreviewed generated reports here.
- Do not promote raw `reports/` directories.
- Do not list artifacts containing secrets.
- Do not make an artifact authoritative without a matching documentation record.
