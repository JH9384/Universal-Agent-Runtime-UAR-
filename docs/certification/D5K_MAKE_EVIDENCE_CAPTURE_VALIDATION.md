# D5K Make Evidence Capture Validation

## Status

D5K validates the Makefile target for live Evidence Pack v2 capture.

## Run ID

`d5k-make-live`

## Target

```bash
make d5h-evidence-capture
```

## Validation Result

- Status: `PASS`
- Live API health preflight passed
- Mission Control captured successfully
- Certification captured successfully
- Latest burn-in captured successfully
- Evidence Pack v2 JSON generated successfully
- Evidence Pack v2 Markdown generated successfully

## Validation Command

```bash
export API_KEYS="local-admin-key:admin:local-d5k"
export UAR_AUTH_MODE="api_key"
python -m uar.boot --services api > /tmp/uar_d5k_api.log 2>&1 &
API_PID=$!

sleep 8

export API_KEY="local-admin-key"
export RUN_ID="d5k-make-live"
make d5h-evidence-capture

kill "$API_PID" || true
```

## Generated Artifacts

- `reports/evidence_pack/live/d5k-make-live/health.json`
- `reports/evidence_pack/live/d5k-make-live/mission_control.json`
- `reports/evidence_pack/live/d5k-make-live/certification.json`
- `reports/evidence_pack/live/d5k-make-live/burnin.json`
- `reports/evidence_pack/live/d5k-make-live/d5k-make-live_evidence_pack.json`
- `reports/evidence_pack/live/d5k-make-live/d5k-make-live_evidence_pack.md`

## Operational Meaning

Operators can now use a Makefile target to capture authenticated live runtime evidence and generate Evidence Pack v2 artifacts without adding an API endpoint.

## Guardrails

- Generated reports remain ignored unless explicitly promoted.
- Capture remains local/script-based.
- No evidence-pack API endpoint is added.
- Runtime state is not mutated by evidence-pack generation.
