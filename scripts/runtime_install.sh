#!/usr/bin/env bash
set -euo pipefail

python -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements-runtime.txt

bash scripts/runtime_env_check.sh
bash scripts/runtime_smoke.sh

echo 'runtime_install_complete=true'
