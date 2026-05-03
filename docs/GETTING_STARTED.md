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
cd apps/api-python
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
fastapi dev main.py
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

The `uar/` package is the authoritative runtime. `apps/api-python/main.py` is deprecated.
