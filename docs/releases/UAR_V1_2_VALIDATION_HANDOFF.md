# UAR v1.2 Validation Handoff

## Status

UAR v1.2 validation hardening is consolidated through D4J.

## Authoritative Validation Tags

| Lane | Tag | Meaning |
| --- | --- | --- |
| D4D | `v1.2.2-d4d-final` | Final D4D validation closure |
| D4E | `v1.2.3-d4e-runtime-smoke` | Repeatable runtime smoke closure |
| D4F | `v1.2.5-d4f-ci-smoke` | CI runtime smoke baseline |
| D4G | `v1.2.8-d4g-ci-verified` | CI regression gates verified |
| D4H | `v1.2.10-d4h-release-ci-final` | Release CI consolidation final |
| D4I | `v1.2.11-d4i-ci-hygiene` | CI hygiene baseline |
| D4J | `v1.2.12-d4j-release-authority-map` | Release authority map |

## Current Release Position

The validation stack now has:

- local warning-clean evidence,
- repeatable runtime smoke,
- CI runtime smoke,
- CI regression gates,
- documented compatibility shim,
- documented Docker deferral,
- documented tag authority.

## Authoritative CI Workflows

- `.github/workflows/d4e-runtime-smoke.yml`
- `.github/workflows/d4g-regression.yml`

## Known Non-Blocking Items

- Docker smoke remains deferred where Docker daemon is unavailable.
- GitHub Actions Node 20 deprecation warnings remain tracked under D4I.
- CI Python remains pinned to `3.12` while package metadata requires `<3.13,>=3.10`.
- `httpx2.py` remains an intentional warning-clean TestClient compatibility shim.

## Release Meaning

UAR v1.2 is now validation-hardened and operator-documented through D4J. Future work should treat `v1.2.12-d4j-release-authority-map` as the latest authoritative validation map unless superseded by a later release tag.

## Guardrails

- Do not reference superseded tags as release authority.
- Do not weaken strict warning gates.
- Do not make Docker mandatory until daemon availability is stable.
- Do not remove `httpx2.py` until dependency behavior allows it.
