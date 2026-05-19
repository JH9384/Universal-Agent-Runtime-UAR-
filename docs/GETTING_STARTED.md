# Getting Started with UAR

UAR is a Universal Agent Runtime: a constrained execution layer over identity-bound objects.

## What you can do today

1. Create objects
2. Register runtimes
3. Execute runtimes against objects
4. Chain runtimes in workflows
5. Trace lineage
6. Run invariant tests

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
uvicorn uar.api.server:app --reload
```

Open:

```text
http://127.0.0.1:8000/docs
```

## Validate the system

From repo root:

```bash
pytest tests/
```

If tests fail, do not add features. Fix the failing invariant first.

## Canonical runtime status

The `uar/` package is the single authoritative runtime. UOR object/runtime
endpoints are mounted by `uar/api/routers/uor.py`; conformance tests live
in `tests/conformance/`.
