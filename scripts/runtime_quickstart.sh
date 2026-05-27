#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate

pip install -r requirements-runtime.txt

bash scripts/runtime_smoke.sh
bash scripts/run_runtime_api.sh
