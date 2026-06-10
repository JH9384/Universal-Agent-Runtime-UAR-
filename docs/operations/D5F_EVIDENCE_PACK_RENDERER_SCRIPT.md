# D5F Evidence Pack Renderer Script

## Status

D5F adds a local Evidence Pack v2 renderer script.

## Purpose

Exercise the D5E read-only core builder and produce local JSON/Markdown artifacts without adding an API surface.

## Script

`scripts/evidence_pack/render_sample_evidence_pack.py`

## Example Command

```bash
python scripts/evidence_pack/render_sample_evidence_pack.py --run-id d5f-sample
```

## Expected Artifacts

- `reports/evidence_pack/d5f-sample_evidence_pack.json`
- `reports/evidence_pack/d5f-sample_evidence_pack.md`

## Operational Meaning

Operators can now render a local Evidence Pack v2 artifact from the read-only builder before the system exposes pack generation through CLI or API layers.

## Guardrails

- Script is local-only.
- Generated reports remain ignored unless explicitly promoted.
- No runtime state is mutated.
- No API endpoint is added in D5F.
