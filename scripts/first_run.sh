#!/usr/bin/env bash
set -euo pipefail

# UAR First Run Wizard
# This script walks a new user from zero → running system → first result

PYTHON=${PYTHON:-python}
API_HOST=${API_HOST:-127.0.0.1}
API_PORT=${API_PORT:-8000}
OLLAMA_HOST=${OLLAMA_HOST:-http://127.0.0.1:11434}

clear

echo "====================================="
echo " UAR FIRST RUN WIZARD"
echo "====================================="
echo ""
echo "This will guide you from zero → first result."
echo ""

# Check Ollama
if ! command -v ollama &> /dev/null; then
  echo "[!] Ollama is not installed"
  echo "Install from: https://ollama.com"
  exit 1
fi

# Check if Ollama is running
if ! curl -s $OLLAMA_HOST > /dev/null; then
  echo "[!] Ollama is not running"
  echo "Run: ollama serve"
  exit 1
fi

# Ensure model exists
MODEL=${OLLAMA_MODEL:-llama3.2:3b}
if ! ollama list | grep -q "$MODEL"; then
  echo "[i] Pulling model: $MODEL"
  ollama pull $MODEL
fi

# Install deps
echo "[i] Installing dependencies..."
$PYTHON -m pip install --upgrade pip
$PYTHON -m pip install -e '.[dev]'

# Start API in background
echo "[i] Starting UAR API..."
uvicorn uar.api.server:app --host "$API_HOST" --port "$API_PORT" > /tmp/uar.log 2>&1 &
API_PID=$!

sleep 2

# Test run
echo ""
echo "[i] Running first task..."
RESPONSE=$(curl -s http://$API_HOST:$API_PORT/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"Explain gravity simply","skills":["ollama_generate"]}')

echo ""
echo "====================================="
echo " RESULT"
echo "====================================="
echo "$RESPONSE"
echo ""
echo "====================================="
echo " SUCCESS"
echo "====================================="
echo "You just ran your first UAR task."
echo ""
echo "API is still running at: http://$API_HOST:$API_PORT"
echo "Logs: /tmp/uar.log"
echo ""
echo "Next: try your own goal or run 'make up-full' for UI"

wait $API_PID
