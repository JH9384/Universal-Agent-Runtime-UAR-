# D5J Evidence Artifact Hygiene

## Status

D5J defines hygiene rules for generated Evidence Pack v2 artifacts.

## Purpose

Keep local evidence-pack outputs useful to operators without accidentally committing generated runtime artifacts, local API captures, or environment-specific data.

## Generated Artifact Paths

Generated evidence artifacts should remain under:

```text
reports/evidence_pack/
```

Live capture artifacts should remain under:

```text
reports/evidence_pack/live/<run-id>/
```

## Default Rule

Generated evidence packs are ignored by default.

Operators should not commit files under `reports/evidence_pack/` unless they are intentionally promoted as release evidence.

## Promotion Rule

A generated evidence pack may be promoted only when all are true:

1. It supports a release, certification, or validation decision.
2. It does not contain secrets or sensitive runtime data.
3. It has a corresponding documentation record under `docs/certification/` or `docs/operations/`.
4. The promotion is explicit in the commit message.

## Promotion Pattern

Preferred promoted artifact location:

```text
docs/certification/artifacts/<lane>/<artifact-name>
```

Do not promote directly from `reports/evidence_pack/` without review.

## Current Evidence Pack Commands

```bash
python scripts/evidence_pack/render_sample_evidence_pack.py --run-id d5f-sample
python scripts/evidence_pack/build_evidence_pack.py --run-id d5g-sample
./scripts/evidence_pack/capture_live_evidence_pack.sh
make d5h-evidence-capture
```

## Known Guardrails

- Generated reports remain ignored unless explicitly promoted.
- Evidence-pack generation must remain read-only.
- Live capture requires explicit API authentication.
- Evidence-pack generation must not create outcomes, update trust, mutate runs, trigger replay, trigger burn-in, or change certification state.

## Supersession Note

`v1.2.22-d5h-live-evidence-capture` recorded the live capture script before validated live capture. The clean D5H authority is `v1.2.23-d5h-live-evidence-validated`.

## Guardrails

- Do not commit `reports/evidence_pack/` by accident.
- Do not store secrets in promoted artifacts.
- Do not make generated artifacts authoritative without a documentation record.
