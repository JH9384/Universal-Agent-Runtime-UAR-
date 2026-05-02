#!/usr/bin/env bash
set -euo pipefail

PYTHON=${PYTHON:-python}
HOST=${API_HOST:-127.0.0.1}
PORT=${API_PORT:-8000}

 echo "[UAR] Installing dependencies"
 $PYTHON -m pip install --upgrade pip
 $PYTHON -m pip install -e '.[dev]'

 echo "[UAR] Starting API at http://$HOST:$PORT"
 exec uvicorn uar.api.server:app --reload --host "$HOST" --port "$PORT"
