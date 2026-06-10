# D4I CI Hygiene and Action Runtime Plan

## Status

D4I opens after D4H release CI consolidation.

## Goal

Remove CI fragility and future-proof GitHub Actions runtime behavior without changing production UAR behavior.

## Source Evidence

- D4F CI runtime smoke passed.
- D4G CI regression gates passed.
- D4H consolidated validation docs and operator checklist.
- GitHub Actions emitted Node 20 deprecation warnings for checkout/setup-python/upload-artifact actions.

## Tasks

1. Track GitHub Actions Node 20 deprecation warnings.
2. Decide whether to pin newer action versions when available.
3. Keep CI Python on `3.12` until package metadata supports newer versions.
4. Document the `httpx2.py` compatibility shim and removal condition.
5. Add a CI hygiene checklist for future release gates.

## Guardrails

- Do not weaken D4G warning gates.
- Do not make Docker required on hosts without Docker daemon availability.
- Do not remove the `httpx2.py` shim until Starlette/FastAPI dependency behavior no longer requires it.
- Do not add runtime features in D4I.
