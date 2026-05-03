#!/usr/bin/env bash
# Local validation sequence for release/v1.0.0.
# Runs foundation + conformance test suites, boots the API, hits smoke
# endpoints, then tears everything down.
#
# Usage:
#   scripts/local_validate.sh           # full sequence
#   PYTHON=python3.11 scripts/local_validate.sh
#   SKIP_CONFORMANCE=1 scripts/local_validate.sh
#   SKIP_API=1 scripts/local_validate.sh
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
API_HOST="${API_HOST:-127.0.0.1}"
API_PORT="${API_PORT:-8000}"
BASE="http://${API_HOST}:${API_PORT}"

log()  { printf '\n\033[1;36m==> %s\033[0m\n' "$*"; }
ok()   { printf '\033[1;32m    ok: %s\033[0m\n' "$*"; }
fail() { printf '\033[1;31m    FAIL: %s\033[0m\n' "$*" >&2; exit 1; }

API_PID=""
cleanup() {
  if [[ -n "$API_PID" ]] && kill -0 "$API_PID" 2>/dev/null; then
    log "Stopping API (pid=$API_PID)"
    kill "$API_PID" 2>/dev/null || true
    wait "$API_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

log "Python interpreter check"
"$PYTHON" -c 'import sys; assert sys.version_info >= (3, 10), f"need >=3.10, got {sys.version_info[:2]}"'
"$PYTHON" --version
ok "python ok"

log "Install package (editable) with dev extras"
"$PYTHON" -m pip install --upgrade pip >/dev/null
"$PYTHON" -m pip install -e '.[dev]' >/dev/null
ok "install ok"

log "Foundation test suite (gates release)"
"$PYTHON" -m pytest tests/test_*.py -q
ok "foundation tests passed"

if [[ -z "${SKIP_CONFORMANCE:-}" ]]; then
  log "Conformance test suite (non-blocking, legacy prototype)"
  "$PYTHON" -m pytest tests/conformance/ -q || fail "conformance suite failed"
  ok "conformance tests passed"
fi

if [[ -n "${SKIP_API:-}" ]]; then
  log "SKIP_API set — done."
  exit 0
fi

log "Starting API at ${BASE}"
"$PYTHON" -m uvicorn uar.api.server:app --host "$API_HOST" --port "$API_PORT" \
  > /tmp/uar_api.log 2>&1 &
API_PID=$!

# Wait for /api/health
for i in $(seq 1 30); do
  if curl -fs "${BASE}/api/health" >/dev/null 2>&1; then
    ok "API up (pid=$API_PID)"
    break
  fi
  sleep 0.5
  if ! kill -0 "$API_PID" 2>/dev/null; then
    cat /tmp/uar_api.log >&2 || true
    fail "API exited before becoming healthy"
  fi
  [[ "$i" == "30" ]] && { cat /tmp/uar_api.log >&2; fail "API never became healthy"; }
done

log "Smoke: GET /api/health"
curl -fsS "${BASE}/api/health" && echo
ok "health ok"

log "Smoke: POST /api/uar/run"
RUN_RESP="$(curl -fsS -X POST "${BASE}/api/uar/run" \
  -H 'Content-Type: application/json' \
  -d '{"goal":"local validate run","skills":["section_sum"]}')"
echo "$RUN_RESP" | "$PYTHON" -m json.tool
echo "$RUN_RESP" | "$PYTHON" -c 'import json,sys; d=json.load(sys.stdin); assert d["status"]=="completed", d' \
  || fail "run did not complete"
ok "run ok"

log "Smoke: POST /api/uar/stream (first 20 lines)"
curl -fsS -N -X POST "${BASE}/api/uar/stream" \
  -H 'Content-Type: application/json' \
  -d '{"goal":"local validate stream","skills":["section_sum"]}' \
  | head -n 20
ok "stream ok"

log "Smoke: GET /api/uar/runs"
curl -fsS "${BASE}/api/uar/runs" | "$PYTHON" -m json.tool | head -n 40
ok "runs list ok"

log "All local validation checks passed"
