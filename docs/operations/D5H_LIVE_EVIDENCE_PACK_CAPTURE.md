# D5H Live Evidence Pack Capture

## Status

D5H adds a local live evidence capture script that gathers authenticated UAR API evidence and builds an Evidence Pack v2 artifact.

## Purpose

Bridge D5G local JSON-input pack generation with live operational evidence while avoiding a new evidence-pack API endpoint.

## Script

`scripts/evidence_pack/capture_live_evidence_pack.sh`

## Required Runtime

The UAR API must be running with API-key auth enabled.

```bash
export API_KEYS="local-admin-key:admin:local-d5h"
export UAR_AUTH_MODE="api_key"
python -m uar.boot --services api
```

## Capture Command

```bash
export API_KEY="local-admin-key"
export RUN_ID="d5h-live"
./scripts/evidence_pack/capture_live_evidence_pack.sh
```

## Captured Inputs

- Mission Control: `/api/uar/mission-control`
- Certification: `/api/uar/certification`
- Latest burn-in: `/api/uar/burnin/latest`

## Generated Artifacts

- `reports/evidence_pack/live/d5h-live/mission_control.json`
- `reports/evidence_pack/live/d5h-live/certification.json`
- `reports/evidence_pack/live/d5h-live/burnin.json`
- `reports/evidence_pack/live/d5h-live/d5h-live_evidence_pack.json`
- `reports/evidence_pack/live/d5h-live/d5h-live_evidence_pack.md`

## Operational Meaning

Operators can now capture live API evidence into an Evidence Pack v2 artifact without mutating runtime state and without adding an API endpoint for evidence packs.

## Guardrails

- Capture is local/script-based.
- Capture requires explicit API authentication.
- Generated reports remain ignored unless explicitly promoted.
- The script does not create outcomes, update trust, mutate runs, trigger replay, trigger burn-in, or change certification state.
