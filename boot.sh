#!/usr/bin/env bash
# UAR Dynamic Boot — API + Web + Dashboard
# Usage:
#   ./boot.sh                    # start all services
#   ./boot.sh api web            # start only API and web
#   API_PORT=8080 WEB_PORT=3000 DASHBOARD_PORT=3001 ./boot.sh
#   PYTHON=python3.11 ./boot.sh
#   NO_BROWSER=1 ./boot.sh       # skip auto-open

set -e

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

# ---- Configuration ----
API_PORT="${API_PORT:-8000}"
WEB_PORT="${WEB_PORT:-5173}"
DASHBOARD_PORT="${DASHBOARD_PORT:-3001}"
PYTHON="${PYTHON:-$(command -v python3.12 || command -v python3.11 || command -v python3.10 || command -v python3)}"

API_URL="http://127.0.0.1:${API_PORT}"
WEB_URL="http://127.0.0.1:${WEB_PORT}"
DASHBOARD_URL="http://127.0.0.1:${DASHBOARD_PORT}"

# ---- Service selection ----
SERVICES="${1:-api web dashboard}"
[ "$#" -eq 0 ] || SERVICES="$@"

echo "═══════════════════════════════════════════════════════════════"
echo "  UAR Dynamic Boot"
echo "  Services: $SERVICES"
echo "  API:      $API_URL"
echo "  Web:      $WEB_URL"
echo "  Dashboard: $DASHBOARD_URL"
echo "  Python:   $PYTHON"
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

# ---- Service discovery helpers ----
has_service() { echo " $SERVICES " | grep -q " $1 "; }
needs_api()   { has_service web || has_service dashboard; }

# ---- Port collision detection ----
port_free() { ! lsof -ti:$1 >/dev/null 2>&1; }
find_free_port() {
    local port=$1
    while ! port_free "$port"; do
        echo "  Port $port in use, trying $((port+1))..." >&2
        port=$((port+1))
    done
    echo "$port"
}

# Check port availability
if ! port_free "$API_PORT"; then
    echo "WARNING: API port $API_PORT is occupied. Attempting to find free port..."
    API_PORT=$(find_free_port "$API_PORT")
    API_URL="http://127.0.0.1:${API_PORT}"
fi

# ---- Cleanup on exit ----
declare -A PIDS
PIDS=()
cleanup() {
    echo ""
    echo "Shutting down UAR services..."
    for name in "${!PIDS[@]}"; do
        pid="${PIDS[$name]}"
        [ -n "$pid" ] && kill "$pid" 2>/dev/null || true
    done
    wait 2>/dev/null || true
    echo "Stopped."
}
trap cleanup EXIT INT TERM

# ---- Start API (required by web and dashboard) ----
start_api() {
    if [ ! -f "uar/api/server.py" ]; then
        echo "ERROR: uar/api/server.py not found"
        return 1
    fi

    echo -n "Starting API on :$API_PORT... "
    $PYTHON -m uvicorn uar.api.server:app --host 127.0.0.1 --port "$API_PORT" \
        > /tmp/uar_api.log 2>&1 &
    PIDS[api]=$!

    for i in $(seq 1 40); do
        if curl -fs "$API_URL/api/health" >/dev/null 2>&1; then
            echo "OK (pid=${PIDS[api]})"
            return 0
        fi
        sleep 0.25
        if ! kill -0 "${PIDS[api]}" 2>/dev/null; then
            echo "FAIL"
            cat /tmp/uar_api.log
            return 1
        fi
    done
    echo "TIMEOUT"
    cat /tmp/uar_api.log
    return 1
}

# ---- Start Web UI ----
start_web() {
    if [ ! -f "apps/web/package.json" ]; then
        echo "SKIP: apps/web/package.json not found"
        return 0
    fi

    if [ ! -d "apps/web/node_modules" ]; then
        echo "Installing web deps (first run)..."
        (cd apps/web && npm install --silent)
    fi

    if ! port_free "$WEB_PORT"; then
        echo "WARNING: Web port $WEB_PORT is occupied. Attempting to find free port..."
        WEB_PORT=$(find_free_port "$WEB_PORT")
        WEB_URL="http://127.0.0.1:${WEB_PORT}"
    fi

    echo -n "Starting Web UI on :$WEB_PORT... "
    (cd apps/web && npm run dev -- --port "$WEB_PORT" --host 127.0.0.1) \
        > /tmp/uar_web.log 2>&1 &
    PIDS[web]=$!

    for i in $(seq 1 40); do
        if curl -fs "$WEB_URL" >/dev/null 2>&1; then
            echo "OK (pid=${PIDS[web]})"
            return 0
        fi
        sleep 0.5
        if ! kill -0 "${PIDS[web]}" 2>/dev/null; then
            echo "FAIL"
            cat /tmp/uar_web.log
            return 1
        fi
    done
    echo "TIMEOUT"
    cat /tmp/uar_web.log
    return 1
}

# ---- Start Dashboard ----
start_dashboard() {
    if [ ! -f "apps/operator-dashboard/package.json" ]; then
        echo "SKIP: apps/operator-dashboard/package.json not found"
        return 0
    fi

    if [ ! -d "apps/operator-dashboard/node_modules" ]; then
        echo "Installing dashboard deps (first run)..."
        (cd apps/operator-dashboard && npm install --silent)
    fi

    if ! port_free "$DASHBOARD_PORT"; then
        echo "WARNING: Dashboard port $DASHBOARD_PORT is occupied. Attempting to find free port..."
        DASHBOARD_PORT=$(find_free_port "$DASHBOARD_PORT")
        DASHBOARD_URL="http://127.0.0.1:${DASHBOARD_PORT}"
    fi

    echo -n "Starting Mission Control on :$DASHBOARD_PORT... "
    (cd apps/operator-dashboard && npm run dev) \
        > /tmp/uar_dashboard.log 2>&1 &
    PIDS[dashboard]=$!

    for i in $(seq 1 40); do
        if curl -fs "$DASHBOARD_URL" >/dev/null 2>&1; then
            echo "OK (pid=${PIDS[dashboard]})"
            return 0
        fi
        sleep 0.5
        if ! kill -0 "${PIDS[dashboard]}" 2>/dev/null; then
            echo "FAIL"
            cat /tmp/uar_dashboard.log
            return 1
        fi
    done
    echo "TIMEOUT"
    cat /tmp/uar_dashboard.log
    return 1
}

# ---- Orchestrate startup ----
if needs_api; then
    has_service api || SERVICES="api $SERVICES"
fi

for svc in $SERVICES; do
    case "$svc" in
        api)       start_api ;;
        web)       start_web ;;
        dashboard) start_dashboard ;;
        *)         echo "Unknown service: $svc" ;;
    esac
done

# ---- Auto-open browser ----
if [ -z "$NO_BROWSER" ]; then
    if has_service web && command -v open >/dev/null; then
        sleep 1 && open "$WEB_URL"
    fi
    if has_service dashboard && command -v open >/dev/null; then
        sleep 1 && open "$DASHBOARD_URL"
    fi
fi

echo ""
echo "───────────────────────────────────────────────────────────────"
echo "  UAR is running"
has_service api       && echo "    API:        $API_URL"
has_service web       && echo "    Web UI:     $WEB_URL"
has_service dashboard && echo "    Dashboard:  $DASHBOARD_URL"
echo "    Health:     $API_URL/api/health"
echo "    Logs:       tail -f /tmp/uar_*.log"
echo ""
echo "  Press Ctrl+C to stop all services."
echo "───────────────────────────────────────────────────────────────"

# Wait for any service to exit
wait
