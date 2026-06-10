# D4E Runtime Smoke Baseline

## Status

D4E runtime smoke validation is repeatable and passed.

## Date

2026-06-09

## Script

`scripts/validate_d4e_runtime_smoke.sh`

## Purpose

The script makes live API smoke capture repeatable without using heredocs or requiring two terminals.

## Runtime Behavior

The script:

- starts the UAR API in the background
- waits for the health endpoint
- captures Mission Control JSON
- captures certification JSON
- runs smoke burn-in through the API
- captures latest burn-in JSON
- writes artifacts under `reports/d4e/`
- validates JSON output
- shuts down the API cleanly

## Expected Artifacts

- `reports/d4e/api.log`
- `reports/d4e/health_live.json`
- `reports/d4e/mission_control.json`
- `reports/d4e/certification.json`
- `reports/d4e/burnin_run.json`
- `reports/d4e/burnin_latest.json`
- `reports/d4e/runtime_smoke_summary.json`

## Validation Command

```bash
./scripts/validate_d4e_runtime_smoke.sh
```

## Expected Result

`D4E runtime smoke: PASS`\n\n## Latest Result\n\n- Status: `PASS`\n- Burn-in passed: `true`\n- Burn-in score: `99`\n- Mission Control JSON captured successfully\n- Certification JSON captured successfully\n- Latest burn-in JSON captured successfully\n- Summary artifact: `reports/d4e/runtime_smoke_summary.json`

## Guardrails

- No production runtime behavior is changed.
- Local API key is for local validation only.
- Generated reports remain ignored unless explicitly force-added.
