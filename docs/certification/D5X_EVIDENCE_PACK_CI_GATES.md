# D5X Evidence Pack CI Gates

## Status

D5X adds CI-visible Evidence Pack v2 contract gates.

## Workflow

`.github/workflows/d5x-evidence-pack.yml`

## CI Runtime

- Python: `3.12`
- Auth mode: `api_key`

## Gates

- `ruff check .`
- `pytest tests/core/test_evidence_pack.py -q`
- `pytest tests/api/test_evidence_pack_router.py -q`
- `pytest tests/api/test_evidence_pack_api_contract.py -q`

## GitHub Actions Evidence

- Run URL: `https://github.com/JH9384/Universal-Agent-Runtime-UAR-/actions/runs/27277558946`
- Conclusion: `success`

## Operational Meaning

Evidence Pack v2 now has CI coverage for the core builder, read-only router, authentication behavior, response contract, markdown option, and missing-data behavior without requiring a live API server.

## Guardrails

- This workflow does not run live curl smoke.
- This workflow does not write or promote artifacts.
- This workflow does not mutate outcomes, trust, runs, replay, burn-in, or certification.
- Live API smoke remains covered by `make d5w-evidence-pack-api-smoke`.
