# D4D Live API Smoke Evidence

## Status

Live API smoke validation captured for D4D.

## Date

2026-06-09

## Runtime

- API command: `python -m uar.boot --services api`
- Auth mode: `api_key`
- Local validation key: `local-admin-key`
- API URL: `http://127.0.0.1:8000`

## Endpoints Checked

- `GET /api/uar/mission-control`
- `GET /api/uar/certification`
- `POST /api/uar/burnin/run`
- `GET /api/uar/burnin/latest`

## Expected Evidence

- Mission Control returns HTTP 200 with authenticated operator access.
- Certification returns HTTP 200 with authenticated operator access.
- Burn-in run executes through the live API.
- Latest burn-in returns the current smoke report after execution.

## Operational Meaning

This validates live authenticated API access for Mission Control, certification, burn-in execution, and latest burn-in retrieval.

## Guardrails

- Local validation key only.
- Do not commit secrets.
- Evidence record only; no production behavior changed.
