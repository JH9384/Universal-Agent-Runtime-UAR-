# D5G Evidence Pack CLI Command

## Status

D5G adds a local Evidence Pack v2 command script that accepts supplied JSON inputs.

## Purpose

Move from a sample renderer to an operator-usable local command while preserving the D5E read-only builder guardrail.

## Script

`scripts/evidence_pack/build_evidence_pack.py`

## Example Command

```bash
python scripts/evidence_pack/build_evidence_pack.py \
  --run-id d5g-sample \
  --mission-control-json /tmp/uar_d5g_inputs/mission_control.json \
  --replay-json /tmp/uar_d5g_inputs/replay.json \
  --burnin-json /tmp/uar_d5g_inputs/burnin.json \
  --certification-json /tmp/uar_d5g_inputs/certification.json
```

## Expected Artifacts

- `reports/evidence_pack/d5g-sample_evidence_pack.json`
- `reports/evidence_pack/d5g-sample_evidence_pack.md`

## Operational Meaning

Operators can now build Evidence Pack v2 artifacts from already-captured JSON evidence without triggering runtime side effects.

## Guardrails

- The command is read-only.
- The command does not fetch live API data yet.
- The command does not mutate outcomes, runs, trust, replay, burn-in, or certification state.
- Missing sections remain explicit through the Evidence Pack availability contract.
