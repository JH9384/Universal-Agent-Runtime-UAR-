# Evidence Pack Operator README

## Status

This README is the operator-facing guide for Evidence Pack v2 generation, live capture, promotion, and lookup.

## Purpose

Evidence Pack v2 turns UAR operational evidence into reviewable artifacts without mutating runtime state.

Canonical path:

```text
Signal -> Mission Control -> Replay -> Evidence Pack -> Outcome -> Trust Movement
```

## Current Capabilities

### 1. Render a Sample Evidence Pack

```bash
python scripts/evidence_pack/render_sample_evidence_pack.py --run-id d5f-sample
```

Outputs:

```text
reports/evidence_pack/d5f-sample_evidence_pack.json
reports/evidence_pack/d5f-sample_evidence_pack.md
```

### 2. Build an Evidence Pack from Supplied JSON

```bash
python scripts/evidence_pack/build_evidence_pack.py \
  --run-id d5g-sample \
  --mission-control-json /path/to/mission_control.json \
  --replay-json /path/to/replay.json \
  --burnin-json /path/to/burnin.json \
  --certification-json /path/to/certification.json
```

### 3. Capture Live API Evidence

Start API:

```bash
export API_KEYS="local-admin-key:admin:local-evidence"
export UAR_AUTH_MODE="api_key"
python -m uar.boot --services api
```

Capture evidence:

```bash
export API_KEY="local-admin-key"
export RUN_ID="operator-evidence"
./scripts/evidence_pack/capture_live_evidence_pack.sh
```

Or use Make:

```bash
make d5h-evidence-capture
```

## Generated Artifact Hygiene

Generated evidence packs live under:

```text
reports/evidence_pack/
```

They are ignored by default and should not be committed unless explicitly promoted.

## Promotion Workflow

Promote only sanitized, reviewed artifacts that support a release, certification, validation, or incident decision.

Preferred destination:

```text
docs/certification/artifacts/<lane>/<run-id>/
```

Promotion pattern:

```bash
mkdir -p docs/certification/artifacts/<lane>/<run-id>

cp reports/evidence_pack/live/<run-id>/<run-id>_evidence_pack.json \
  docs/certification/artifacts/<lane>/<run-id>/

cp reports/evidence_pack/live/<run-id>/<run-id>_evidence_pack.md \
  docs/certification/artifacts/<lane>/<run-id>/
```

Secret scan before commit:

```bash
rg -n "local-admin-key|API_KEYS|Authorization|Bearer|OPENAI_API_KEY|password|secret|token" \
  docs/certification/artifacts/<lane>/<run-id>/ || true
```

If artifacts are ignored by `.gitignore`, add intentionally:

```bash
git add -f docs/certification/artifacts/<lane>/<run-id>/
```

## Promotion Index

Promoted evidence packs are listed here:

```text
docs/certification/EVIDENCE_PACK_PROMOTION_INDEX.md
```

## Current Authoritative Evidence Pack Tags

| Lane | Tag | Meaning |
| --- | --- | --- |
| D5E | `v1.2.19-d5e-evidence-pack-builder` | Read-only core builder |
| D5F | `v1.2.20-d5f-evidence-pack-renderer` | Sample renderer script |
| D5G | `v1.2.21-d5g-evidence-pack-cli` | JSON-input builder command |
| D5H | `v1.2.23-d5h-live-evidence-validated` | Live capture validated |
| D5I | `v1.2.24-d5i-evidence-capture-make-target` | Make target added |
| D5J | `v1.2.25-d5j-evidence-artifact-hygiene` | Artifact hygiene |
| D5K | `v1.2.26-d5k-make-evidence-capture` | Make target validation |
| D5L | `v1.2.27-d5l-evidence-promotion-template` | Promotion template |
| D5M | `v1.2.32-d5m-final-artifact-authority` | Promoted artifact authority |
| D5N | `v1.2.33-d5n-evidence-promotion-index` | Promotion index |

## Guardrails

- Evidence pack generation must remain read-only.
- Do not commit generated `reports/evidence_pack/` output by accident.
- Do not promote artifacts containing secrets.
- Do not add an evidence-pack API endpoint until the local/operator workflow is stable.
- Do not mutate outcomes, trust, runs, replay, burn-in, or certification during pack generation.
