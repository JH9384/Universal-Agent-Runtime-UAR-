# D4I CI Hygiene Baseline

## Status

D4I's original baseline is retained below. The current branch adds an action
runtime, lint, frontend dependency, and performance-gate hygiene delta that
requires fresh GitHub Actions evidence before certification is advanced.

## Date

2026-06-10

## GitHub Actions Evidence

- Workflow: `D4G Regression Gates`
- Run URL: `https://github.com/JH9384/Universal-Agent-Runtime-UAR-/actions/runs/27274305504`
- Conclusion: `success`

## Evidence Captured

- D4I CI hygiene plan exists.
- D4I CI hygiene checklist exists.
- HTTPX2 compatibility shim is documented.
- D4G regression gates remain active after D4I documentation updates.

## Current Hygiene Delta

- Node 24 action/runtime line across maintained workflows and frontend jobs.
- Explicit Ruff E/W/F selection with zero current violations.
- Coverage excludes wall-clock performance tests; a dedicated performance job
  remains blocking.
- Frontend dependency installs, tests, builds, and audits are independently gated.

## Authoritative Tags

- D4F: `v1.2.5-d4f-ci-smoke`
- D4G: `v1.2.8-d4g-ci-verified`
- D4H: `v1.2.10-d4h-release-ci-final`

## Guardrails

- Do not weaken strict warning gates.
- Do not make Docker mandatory while daemon availability is unstable.
- Do not remove `httpx2.py` until dependency behavior allows it.
- Do not add runtime features in D4I.
