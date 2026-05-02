#!/usr/bin/env bash
set -euo pipefail

PYTHON=${PYTHON:-python3.11}
API_HOST=${API_HOST:-127.0.0.1}
API_PORT=${API_PORT:-8000}
WEB_HOST=${WEB_HOST:-127.0.0.1}
WEB_PORT=${WEB_PORT:-5173}
OLLAMA_MODEL=${OLLAMA_MODEL:-llama3.2:3b}
OLLAMA_HOST=${OLLAMA_HOST:-http://127.0.0.1:11434}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

API_PID=""
WEB_PID=""

cleanup() {
  echo ""
  echo "🛑 Shutting down UAR quickstart..."
  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    kill "${API_PID}" 2>/dev/null || true
  fi
  if [[ -n "${WEB_PID}" ]] && kill -0 "${WEB_PID}" 2>/dev/null; then
    kill "${WEB_PID}" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

open_url() {
  local url="$1"
  if command -v open >/dev/null 2>&1; then
    open "$url" || true
  elif command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" || true
  else
    echo "Open this in your browser: $url"
  fi
}

wait_for_url() {
  local url="$1"
  local name="$2"
  local attempts=60
  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      echo "✅ $name is ready: $url"
      return 0
    fi
    sleep 1
  done
  echo "❌ Timed out waiting for $name at $url"
  return 1
}

find_web_url() {
  for port in 5173 5174 5175 5176 5177; do
    if curl -fsS "http://${WEB_HOST}:${port}" >/dev/null 2>&1; then
      echo "http://${WEB_HOST}:${port}"
      return 0
    fi
  done
  echo "http://${WEB_HOST}:${WEB_PORT}"
}

echo "🚀 UAR One-Command Quickstart"
echo "Project: $ROOT_DIR"
echo "Python:  $PYTHON"
echo "API:     http://${API_HOST}:${API_PORT}"
echo "Ollama:  ${OLLAMA_HOST} (${OLLAMA_MODEL})"
echo ""

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "❌ $PYTHON not found. Install Python 3.11 or run: PYTHON=python3 scripts/quickstart.sh"
  exit 1
fi

if ! command -v npm >/dev/null 2>&1; then
  echo "❌ npm not found. Install Node.js before launching the web UI."
  exit 1
fi

if command -v ollama >/dev/null 2>&1; then
  if curl -fsS "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
    echo "✅ Ollama is already running"
  else
    echo "🧠 Starting Ollama in the background..."
    ollama serve >/tmp/uar-ollama.log 2>&1 &
    sleep 3
  fi
  echo "📦 Ensuring Ollama model exists: ${OLLAMA_MODEL}"
  ollama pull "${OLLAMA_MODEL}" || true
else
  echo "⚠️ Ollama not found. The UI/API will start, but ollama_generate will fail until Ollama is installed."
fi

echo "📦 Installing Python dependencies..."
"$PYTHON" -m pip install --upgrade pip
"$PYTHON" -m pip install -e '.[dev]'

echo "📦 Installing web dependencies..."
(cd apps/web && npm install)

echo "⚙️ Starting UAR API..."
uvicorn uar.api.server:app --host "$API_HOST" --port "$API_PORT" >/tmp/uar-api.log 2>&1 &
API_PID=$!
wait_for_url "http://${API_HOST}:${API_PORT}/api/uar/runs" "UAR API"

echo "🎨 Starting UAR web UI..."
(cd apps/web && npm run dev -- --host "$WEB_HOST" --port "$WEB_PORT") >/tmp/uar-web.log 2>&1 &
WEB_PID=$!
sleep 3
WEB_URL="$(find_web_url)"
echo "✅ UAR web UI is ready: ${WEB_URL}"

echo "🧪 Running smoke check through UAR API..."
curl -fsS "http://${API_HOST}:${API_PORT}/api/uar/run" \
  -H "Content-Type: application/json" \
  -d '{"goal":"Say hello from UAR","skills":["section_sum"]}' >/tmp/uar-smoke.json

echo "✅ Smoke check passed"
echo "🌐 Opening browser: ${WEB_URL}"
open_url "${WEB_URL}"

echo ""
echo "UAR is running."
echo "API: ${API_HOST}:${API_PORT}"
echo "UI:  ${WEB_URL}"
echo "Logs: /tmp/uar-api.log and /tmp/uar-web.log"
echo "Press Ctrl+C here to stop API and UI."

while true; do
  sleep 3600
done
