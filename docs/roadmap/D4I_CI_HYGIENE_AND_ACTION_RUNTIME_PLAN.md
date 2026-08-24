# D4I CI Hygiene and Action Runtime Plan

## Status

D4I action-runtime and lint hygiene is implemented; fresh CI evidence remains
the closure authority.

## Goal

Remove CI fragility and future-proof GitHub Actions runtime behavior without changing production UAR behavior.

## Source Evidence

- D4F CI runtime smoke passed.
- D4G CI regression gates passed.
- D4H consolidated validation docs and operator checklist.
- GitHub Actions emitted Node 20 deprecation warnings for
  checkout/setup-python/upload-artifact actions.
- Workflows now use the Node 24 action runtime line and Node 24 frontend jobs.
- The E/W/F lint contract is explicit, and its pre-existing E501 debt is clean.
- Wall-clock performance tests run separately from coverage instrumentation.

## Tasks

1. Confirm the upgraded action runtimes emit no Node 20 warnings.
2. Keep action majors and frontend Node versions aligned on the Node 24 line.
3. Keep CI Python on `3.12` until package metadata supports newer versions.
4. Document the `httpx2.py` compatibility shim and removal condition.
5. Add a CI hygiene checklist for future release gates.
6. Require dedicated, non-coverage performance evidence before signing.

## Guardrails

- Do not weaken D4G warning gates.
- Do not make Docker required on hosts without Docker daemon availability.
- Do not remove the `httpx2.py` shim until Starlette/FastAPI dependency behavior no longer requires it.
- Do not add runtime features in D4I.
