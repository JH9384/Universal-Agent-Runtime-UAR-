# D4J Release Authority Map

## Status

D4J opens after D4I CI hygiene baseline is recorded and tagged.

## Purpose

Provide one canonical operator-facing map of authoritative validation tags, superseded tags, CI gates, and release evidence documents.

## Authoritative Tags

| Lane | Authoritative Tag | Meaning |
| --- | --- | --- |
| D4D | `v1.2.2-d4d-final` | Final D4D validation closure |
| D4E | `v1.2.3-d4e-runtime-smoke` | Repeatable runtime smoke closure |
| D4F | `v1.2.5-d4f-ci-smoke` | CI runtime smoke baseline |
| D4G | `v1.2.8-d4g-ci-verified` | CI regression gates verified |
| D4H | `v1.2.10-d4h-release-ci-final` | Release CI consolidation final |
| D4I | `v1.2.11-d4i-ci-hygiene` | CI hygiene baseline |

## Superseded / Non-Authoritative Tags

| Tag | Reason |
| --- | --- |
| `v1.2.1-d4d-validated` | Superseded by D4D final tag |
| `v1.2.6-d4g-ci-regression` | Created before CI success was verified |
| `v1.2.7-d4g-ci-confirmed` | Created before CI success was verified |
| `v1.2.9-d4h-release-ci-consolidated` | Superseded by D4H final tag |

## Authoritative CI Workflows

- `.github/workflows/d4e-runtime-smoke.yml`
- `.github/workflows/d4g-regression.yml`

## Current CI Runtime Decisions

- CI Python is pinned to `3.12` while package metadata requires `<3.13,>=3.10`.
- `httpx2.py` remains as a compatibility shim for Starlette TestClient warning-clean collection.
- Docker smoke remains deferred when Docker daemon availability is not present.

## Guardrails

- Use authoritative tags for release references.
- Do not delete superseded tags; document them.
- Do not weaken warning gates.
- Do not make Docker mandatory until daemon availability is stable.
