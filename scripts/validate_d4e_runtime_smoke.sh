#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:-local-admin-key}"
REPORT_DIR="${REPORT_DIR:-reports/d4e}"
PID_FILE="${REPORT_DIR}/uar_api.pid"

mkdir -p "$REPORT_DIR"

export API_KEYS="${API_KEYS:-local-admin-key:admin:local-d4e}"
export UAR_AUTH_MODE="${UAR_AUTH_MODE:-api_key}"

cleanup() {
  if [[ -f "$PID_FILE" ]]; then
    pid="$(cat "$PID_FILE" || true)"
    if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
      kill "$pid" || true
      wait "$pid" 2>/dev/null || true
    fi
    rm -f "$PID_FILE"
  fi
}
trap cleanup EXIT

if lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  echo "Port 8000 is already in use. Stop the existing process before running this smoke script." >&2
  lsof -nP -iTCP:8000 -sTCP:LISTEN >&2 || true
  exit 2
fi

python -m uar.boot --services api > "${REPORT_DIR}/api.log" 2>&1 &
echo "$!" > "$PID_FILE"

for _ in $(seq 1 60); do
  if curl -sS "${API_URL}/api/health/live" >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

curl -fsS "${API_URL}/api/health/live" > "${REPORT_DIR}/health_live.json"

curl -fsS -H "Authorization: Bearer ${API_KEY}"   "${API_URL}/api/uar/mission-control"   > "${REPORT_DIR}/mission_control.json"

curl -fsS -H "Authorization: Bearer ${API_KEY}"   "${API_URL}/api/uar/certification"   > "${REPORT_DIR}/certification.json"

curl -fsS -X POST -H "Authorization: Bearer ${API_KEY}"   "${API_URL}/api/uar/burnin/run"   > "${REPORT_DIR}/burnin_run.json"

curl -fsS -H "Authorization: Bearer ${API_KEY}"   "${API_URL}/api/uar/burnin/latest"   > "${REPORT_DIR}/burnin_latest.json"

python -m json.tool "${REPORT_DIR}/mission_control.json" >/dev/null
python -m json.tool "${REPORT_DIR}/certification.json" >/dev/null
python -m json.tool "${REPORT_DIR}/burnin_run.json" >/dev/null
python -m json.tool "${REPORT_DIR}/burnin_latest.json" >/dev/null

REPORT_DIR="${REPORT_DIR}" python scripts/d4e/write_runtime_smoke_summary.py

echo "D4E runtime smoke: PASS"
