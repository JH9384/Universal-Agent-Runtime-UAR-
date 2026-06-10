# D5M Evidence Pack Promotion Smoke

## Status

D5M validates the Evidence Pack v2 promotion path using a sanitized generated sample artifact.

## Run ID

`d5m-promotion-smoke`

## Purpose

Prove that ignored generated evidence packs can be intentionally promoted into tracked certification artifacts using the D5L promotion template.

## Source Command

```bash
python scripts/evidence_pack/render_sample_evidence_pack.py --run-id d5m-promotion-smoke
```

## Promotion Destination

```text
docs/certification/artifacts/d5m/d5m-promotion-smoke/
```

## Promoted Artifacts

- `docs/certification/artifacts/d5m/d5m-promotion-smoke/d5m-promotion-smoke_evidence_pack.json`
- `docs/certification/artifacts/d5m/d5m-promotion-smoke/d5m-promotion-smoke_evidence_pack.md`

## Review Result

Secret/sensitive-value scan completed against the promoted artifact directory.

Pattern set:

```text
local-admin-key|API_KEYS|Authorization|Bearer|OPENAI_API_KEY|password|secret|token
```

Expected result: no matches.

## Operational Meaning

D5M proves the evidence-pack promotion path works without promoting raw `reports/` folders and without relying on live runtime data.

## Guardrails

- Only sanitized artifacts were promoted.
- Raw `reports/` artifacts remain ignored by default.
- Promotion does not mutate runtime state.
- Promoted artifacts require matching documentation.

## Supersession Note

`v1.2.28-d5m-evidence-promotion-smoke` was created before the promoted artifacts were committed. The clean D5M authority tag is `v1.2.29-d5m-evidence-promotion-validated`.

## Final Authority Note

`v1.2.31-d5m-promoted-artifacts-committed` is the authoritative D5M tag because it includes the promoted JSON and Markdown artifacts. Earlier D5M tags recorded the promotion flow but did not include the force-added ignored artifact files.
