# D4D Live API Certification Package

## Status

Live API certification package export validated.

## Date

2026-06-09

## Runtime

- API: `python -m uar.boot --services api`
- Auth mode: `api_key`
- Local validation key: `local-admin-key`
- API URL: `http://127.0.0.1:8000`

## Validation Command

```bash
export API_KEYS="local-admin-key:admin:local-d4d"
export UAR_AUTH_MODE="api_key"

python scripts/hardening/certification_package.py \
  --api-url http://127.0.0.1:8000 \
  --api-key local-admin-key \
  --output reports/certification/d4d_live_api_certification_package.json
```

## Expected Artifact

- `reports/certification/d4d_live_api_certification_package.json`

## Prior Finding

A previous unauthenticated export attempt returned `401 Unauthorized` for protected endpoints. That result is expected and confirms the certification package uses guarded operational endpoints.

## Operational Meaning

This validates live API evidence export with explicit operator authentication, moving D4D from local test evidence into authenticated runtime artifact generation.

## Guardrails

- The local validation API key is for local D4D evidence only.
- Do not commit secrets.
- No production runtime behavior is changed by this evidence record.
