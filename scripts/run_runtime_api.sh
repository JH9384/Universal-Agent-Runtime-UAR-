#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-.}"

python -m uvicorn uar.server.runtime_api:app --host 127.0.0.1 --port 8080 --reload
