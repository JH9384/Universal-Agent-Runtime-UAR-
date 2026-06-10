# D5L Evidence Pack Promotion Template

## Status

D5L defines the safe promotion path for Evidence Pack v2 artifacts.

## Purpose

Generated evidence packs are ignored by default under `reports/evidence_pack/`. This template defines when and how an operator may promote a generated pack into tracked certification evidence.

## Default Rule

Do not commit generated files from:

```text
reports/evidence_pack/
```

Generated evidence packs are local operational artifacts unless explicitly promoted.

## Promotion Criteria

An Evidence Pack v2 artifact may be promoted only when all are true:

1. It supports a release, certification, validation, or incident decision.
2. It contains no secrets, API keys, credentials, private tokens, or sensitive runtime payloads.
3. It has been reviewed by an operator.
4. It has a matching documentation record.
5. The commit message clearly says the artifact is promoted evidence.

## Promotion Destination

Preferred destination:

```text
docs/certification/artifacts/<lane>/<run-id>/
```

Example:

```text
docs/certification/artifacts/d5k/d5k-make-live/
```

## Promotion Command Pattern

```bash
mkdir -p docs/certification/artifacts/<lane>/<run-id>

cp reports/evidence_pack/live/<run-id>/<run-id>_evidence_pack.json \
  docs/certification/artifacts/<lane>/<run-id>/

cp reports/evidence_pack/live/<run-id>/<run-id>_evidence_pack.md \
  docs/certification/artifacts/<lane>/<run-id>/

git add docs/certification/artifacts/<lane>/<run-id>/
git commit -m "docs(certification): promote <lane> evidence pack artifact"
```

## Required Review Checklist

Before promotion, check:

```bash
rg -n "local-admin-key|API_KEYS|Authorization|Bearer|OPENAI_API_KEY|password|secret|token" \
  docs/certification/artifacts/<lane>/<run-id>/ || true
```

The review must show no secrets or sensitive values.

## Metadata to Record

The matching certification doc should record:

- run ID
- source command
- generated artifact path
- promotion destination
- validation result
- operator decision
- known unavailable sections

## Guardrails

- Do not promote raw `reports/` folders.
- Do not promote artifacts containing secrets.
- Do not make promoted artifacts authoritative without a matching documentation record.
- Do not mutate runtime state during promotion.
