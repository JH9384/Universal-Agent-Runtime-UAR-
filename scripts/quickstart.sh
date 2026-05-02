#!/usr/bin/env bash
set -e

echo "🚀 UAR Quickstart"

# Check Python
if ! command -v python3 &> /dev/null; then
  echo "❌ Python not found. Please install Python 3.10+"
  exit 1
fi

# Check Ollama
if ! command -v ollama &> /dev/null; then
  echo "❌ Ollama not found. Install from https://ollama.com"
  exit 1
fi

echo "📦 Pulling model (if not already)..."
ollama pull llama3.2:3b || true

echo "🧠 Starting Ollama (background)..."
ollama serve &
sleep 2

echo "📦 Installing Python dependencies..."
python3 -m pip install --upgrade pip
python3 -m pip install -e '.[dev]'

echo "⚙️ Starting UAR API..."
uvicorn uar.api.server:app --host 127.0.0.1 --port 8000 &
sleep 3

echo "🧪 Running first test..."
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{"goal":"Say hello from UAR","skills":["ollama_generate"]}'

echo "\n✅ If you see a response above, you're fully onboarded!"
