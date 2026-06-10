# HTTPX2 Compatibility Shim

## Status

`httpx2.py` is an intentional test/CI compatibility shim.

## Reason

GitHub Actions D4G unit collection failed under strict warning gates because Starlette TestClient attempted to import `httpx2`, then emitted a deprecation warning when falling back to `httpx`.

Strict D4G gates treat that warning as an error.

## Implementation

`httpx2.py` re-exports `httpx` so Starlette TestClient can import `httpx2` without triggering the fallback warning.

## Validation Evidence

- Local targeted middleware test passed: `91 passed`
- D4G CI regression gates passed after the shim was added.
- Authoritative verification tag: `v1.2.8-d4g-ci-verified`

## Removal Condition

Remove this shim only when one of the following is true:

1. Starlette/FastAPI no longer attempts `import httpx2` during TestClient collection.
2. A real supported `httpx2` package/module is available and compatible.
3. UAR no longer uses Starlette/FastAPI TestClient in warning-clean gates.

## Guardrails

- Do not remove while D4G warning-clean CI depends on it.
- Do not weaken warning gates to avoid this issue.
- Do not treat the shim as production runtime behavior.
