#!/usr/bin/env bash
# UAR Single-Command Startup Script
# Usage: ./start.sh [port] [python]
#   ./start.sh                    # default port 8000, auto-detect python
#   ./start.sh 8080               # custom port
#   ./start.sh 8000 python3.11    # specific python

set -e

PORT="${1:-8000}"
PYTHON="${2:-$(command -v python3.10 || command -v python3.11 || command -v python3 || echo python3)}"

echo "═══════════════════════════════════════════════════════════════"
echo "  UAR Startup"
echo "  Python: $PYTHON"
echo "  Port:   $PORT"
echo "═══════════════════════════════════════════════════════════════"

# Verify Python version
echo -n "Checking Python >= 3.10... "
$PYTHON -c 'import sys; exit(0 if sys.version_info >= (3,10) else 1)' || {
    echo "FAIL"
    echo "Error: Python 3.10+ required"
    exit 1
}
echo "OK"

# Install if needed
echo -n "Installing dependencies... "
$PYTHON -m pip install -q -e '.[dev]' 2>/dev/null || {
    echo "FAIL"
    echo "Error: pip install failed"
    exit 1
}
echo "OK"

# Quick test
echo -n "Running quick validation... "
$PYTHON -m pytest tests/test_api.py tests/test_pipeline.py -q --tb=no 2>/dev/null || {
    echo "WARNING (some tests failed, continuing)"
}
echo "OK"

echo ""
echo "Starting UAR API server..."
echo "  Health:  http://127.0.0.1:$PORT/api/health"
echo "  Run:     curl -X POST http://127.0.0.1:$PORT/api/uar/run \\"
echo "           -H 'Content-Type: application/json' \\"
echo "           -d '{\"goal\":\"Hello\",\"skills\":[\"section_sum\"]}'"
echo ""
echo "Press Ctrl+C to stop"
echo "───────────────────────────────────────────────────────────────"

exec $PYTHON -m uvicorn uar.api.server:app --host 127.0.0.1 --port "$PORT" --reload
