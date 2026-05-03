#!/usr/bin/env bash
# UAR Full-Stack Single Boot: API + Web UI + auto-open browser
# Usage:
#   ./boot.sh                         # default: API 8000, Web 5173
#   API_PORT=8080 WEB_PORT=3000 ./boot.sh
#   PYTHON=python3.11 ./boot.sh
#   NO_BROWSER=1 ./boot.sh            # skip auto-open

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
PYTHON="${PYTHON:-$(command -v python3.11 || command -v python3.10 || command -v python3)}"
WEB_URL="http://localhost:${WEB_PORT}"
API_URL="http://127.0.0.1:${API_PORT}"

echo "═══════════════════════════════════════════════════════════════"
echo "  UAR Full-Stack Boot"
echo "  API:     $API_URL"
echo "  Web UI:  $WEB_URL"
echo "  Python:  $PYTHON"
echo "═══════════════════════════════════════════════════════════════"

# ---- Prereq checks ----
command -v node >/dev/null || { echo "ERROR: node not found (install from nodejs.org)"; exit 1; }
command -v npm  >/dev/null || { echo "ERROR: npm not found"; exit 1; }
$PYTHON -c 'import sys; exit(0 if sys.version_info>=(3,10) else 1)' \
    || { echo "ERROR: Python 3.10+ required"; exit 1; }

# ---- Python install ----
echo -n "Installing Python deps... "
$PYTHON -m pip install -q -e '.[dev]' 2>/dev/null
echo "OK"

# ---- Web install ----
if [ ! -d "apps/web/node_modules" ]; then
    echo "Installing web deps (first run)..."
    (cd apps/web && npm install --silent)
fi

# ---- Cleanup on exit ----
API_PID=""
WEB_PID=""
cleanup() {
    echo ""
    echo "Shutting down..."
    [ -n "$WEB_PID" ] && kill "$WEB_PID" 2>/dev/null || true
    [ -n "$API_PID" ] && kill "$API_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo "Stopped."
}
trap cleanup EXIT INT TERM

# ---- Start API ----
echo -n "Starting API on :$API_PORT... "
$PYTHON -m uvicorn uar.api.server:app --host 127.0.0.1 --port "$API_PORT" \
    > /tmp/uar_api.log 2>&1 &
API_PID=$!

for i in $(seq 1 40); do
    if curl -fs "$API_URL/api/health" >/dev/null 2>&1; then
        echo "OK (pid=$API_PID)"
        break
    fi
    sleep 0.25
    if ! kill -0 "$API_PID" 2>/dev/null; then
        echo "FAIL"
        cat /tmp/uar_api.log
        exit 1
    fi
    [ "$i" = "40" ] && { echo "TIMEOUT"; cat /tmp/uar_api.log; exit 1; }
done

# ---- Start Web ----
echo -n "Starting Web UI on :$WEB_PORT... "
(cd apps/web && npm run dev -- --port "$WEB_PORT" --host 127.0.0.1) \
    > /tmp/uar_web.log 2>&1 &
WEB_PID=$!

for i in $(seq 1 40); do
    if curl -fs "$WEB_URL" >/dev/null 2>&1; then
        echo "OK (pid=$WEB_PID)"
        break
    fi
    sleep 0.5
    if ! kill -0 "$WEB_PID" 2>/dev/null; then
        echo "FAIL"
        cat /tmp/uar_web.log
        exit 1
    fi
    [ "$i" = "40" ] && { echo "TIMEOUT"; cat /tmp/uar_web.log; exit 1; }
done

# ---- Auto-open browser ----
if [ -z "$NO_BROWSER" ]; then
    if command -v open >/dev/null; then
        open "$WEB_URL"
    elif command -v xdg-open >/dev/null; then
        xdg-open "$WEB_URL"
    fi
fi

echo ""
echo "───────────────────────────────────────────────────────────────"
echo "  UAR is running"
echo "    Web UI:   $WEB_URL"
echo "    API:      $API_URL"
echo "    Health:   $API_URL/api/health"
echo "    Logs:     tail -f /tmp/uar_api.log /tmp/uar_web.log"
echo ""
echo "  Press Ctrl+C to stop both."
echo "───────────────────────────────────────────────────────────────"

# Wait for either to exit
wait
