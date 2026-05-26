#!/usr/bin/env bash
set -euo pipefail

python --version
pip --version

python - <<'PY'
import importlib

required = ['fastapi', 'uvicorn']
missing = []

for name in required:
    try:
        importlib.import_module(name)
    except Exception:
        missing.append(name)

if missing:
    raise SystemExit(f'Missing dependencies: {missing}')

print('runtime_environment_ok=true')
PY
