#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="$ROOT_DIR/apps/api-python"
WEB_DIR="$ROOT_DIR/apps/web"
PYTHON_BIN="${PYTHON_BIN:-python3.11}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"

API_URL="http://${API_HOST}:${API_PORT}"
WEB_URL="http://localhost:${WEB_PORT}"

cleanup() {
  echo ""
  echo "Stopping UAR dev services..."
  if [[ -n "${API_PID:-}" ]] && kill -0 "$API_PID" 2>/dev/null; then
    kill "$API_PID" 2>/dev/null || true
  fi
  if [[ -n "${WEB_PID:-}" ]] && kill -0 "$WEB_PID" 2>/dev/null; then
    kill "$WEB_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

wait_for_health() {
  local attempts=40
  local delay=0.5
  for ((i=1; i<=attempts; i++)); do
    if curl -fsS "$API_URL/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep "$delay"
  done
  echo "API did not become healthy at $API_URL/health" >&2
  echo "--- API log tail ---" >&2
  tail -80 "$ROOT_DIR/.uar-api.log" >&2 || true
  exit 1
}

require_cmd "$PYTHON_BIN"
require_cmd npm
require_cmd curl

if [[ ! -f "$API_DIR/main.py" ]]; then
  echo "Cannot find API app at $API_DIR/main.py" >&2
  exit 1
fi

if [[ ! -f "$WEB_DIR/package.json" ]]; then
  echo "Cannot find web app at $WEB_DIR/package.json" >&2
  exit 1
fi

if [[ ! -f "$WEB_DIR/index.html" ]]; then
  echo "Missing $WEB_DIR/index.html. Pull latest recovery branch." >&2
  exit 1
fi

if [[ ! -f "$WEB_DIR/src/main.tsx" ]]; then
  echo "Missing $WEB_DIR/src/main.tsx. Pull latest recovery branch." >&2
  exit 1
fi

echo "UAR dev boot"
echo "Root: $ROOT_DIR"
echo "Python: $($PYTHON_BIN --version)"
echo "API: $API_URL"
echo "Web: $WEB_URL"
echo ""

echo "Installing backend dependencies..."
(
  cd "$API_DIR"
  "$PYTHON_BIN" -m pip install -r requirements.txt
)

echo "Installing frontend dependencies..."
(
  cd "$WEB_DIR"
  npm install
)

echo "Starting backend..."
(
  cd "$API_DIR"
  "$PYTHON_BIN" -m uvicorn main:app --host "$API_HOST" --port "$API_PORT" --reload
) > "$ROOT_DIR/.uar-api.log" 2>&1 &
API_PID=$!

wait_for_health

echo "Backend healthy: $API_URL/health"

echo "Starting frontend..."
(
  cd "$WEB_DIR"
  npm run dev -- --host 127.0.0.1 --port "$WEB_PORT"
) > "$ROOT_DIR/.uar-web.log" 2>&1 &
WEB_PID=$!

sleep 2
if ! kill -0 "$WEB_PID" 2>/dev/null; then
  echo "Frontend failed to start." >&2
  echo "--- Web log tail ---" >&2
  tail -80 "$ROOT_DIR/.uar-web.log" >&2 || true
  exit 1
fi

echo ""
echo "UAR is running."
echo "Backend: $API_URL/health"
echo "Frontend: $WEB_URL"
echo ""
echo "Walkthrough: Add 5, Add 10, select both, Run, Trace, Verify."
echo ""
echo "Logs:"
echo "  API: $ROOT_DIR/.uar-api.log"
echo "  Web: $ROOT_DIR/.uar-web.log"
echo ""
echo "Press Ctrl+C here to stop both services."

wait
