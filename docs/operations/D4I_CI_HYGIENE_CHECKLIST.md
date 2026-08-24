# D4I CI Hygiene Checklist

## Status

D4I implementation is complete locally and awaits fresh CI closure evidence.

## Current Known CI Hygiene Items

1. GitHub Actions use the Node 24 runtime line; fresh runs must confirm the old
   deprecation warning is absent.
2. CI Python remains pinned to `3.12` because UAR package metadata requires `<3.13,>=3.10`.
3. `httpx2.py` compatibility shim is required for Starlette TestClient warning-clean collection.
4. Docker smoke remains deferred where Docker daemon is unavailable.
5. Performance tests are isolated from coverage and random-order instrumentation.
6. React, Svelte, and operator-dashboard lockfiles must pass `npm audit`.

## Current Authoritative Workflows

- `.github/workflows/d4e-runtime-smoke.yml`
- `.github/workflows/d4g-regression.yml`

## Current Authoritative Tags

- D4F: `v1.2.5-d4f-ci-smoke`
- D4G: `v1.2.8-d4g-ci-verified`
- D4H: `v1.2.10-d4h-release-ci-final`

## Validation Commands

```bash
make d4e-runtime-smoke
ruff check uar/ tests/ --select=E,W,F
ulimit -n 8192
```

## Removal Conditions

### `httpx2.py`

Remove only when Starlette/FastAPI TestClient no longer emits warning-clean collection failures without it.

### Python `3.12` CI Pin

Relax only when package metadata and dependencies support the newer runtime.

### Docker Deferral

Close only when Docker daemon availability is confirmed and Docker smoke passes.

### Action Runtime

Regress only with explicit evidence that the replacement action supports the
same permissions, cache, and artifact behavior.

## Guardrails

- Do not weaken strict warning gates.
- Do not delete superseded tags; document authority instead.
- Do not add runtime features in D4I.
