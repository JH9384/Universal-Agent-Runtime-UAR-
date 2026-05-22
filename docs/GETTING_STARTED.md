# Getting Started with UAR

**Prerequisites:** Python 3.10+, 5 minutes

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/JH9384/Universal-Agent-Runtime-UAR-.git
cd Universal-Agent-Runtime-UAR-

# 2. Configure
cp .env.minimal .env

# 3. Install
pip install -e .

# 4. Run
python -m uvicorn uar.api.server:app --reload
```

Open `http://127.0.0.1:8000/docs` for the interactive API explorer.

---

## Your First API Call

### Run a Goal (HTTP)

```bash
curl -X POST http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Summarize this project",
    "skills": ["doc_ingest", "section_sum"]
  }'
```

**Response:**

```json
{
  "run_id": "uuid-here",
  "status": "completed",
  "outputs": [...],
  "events": [...]
}
```

### Stream Events (WebSocket)

```bash
curl -N http://localhost:8000/api/uar/stream \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Analyze this codebase",
    "skills": ["dependency_map"]
  }'
```

Or via WebSocket:

```javascript
const ws = new WebSocket("ws://localhost:8000/api/uar/stream/ws");
ws.onopen = () => {
  ws.send(JSON.stringify({
    goal: "Hello world",
    skills: ["ollama_generate"]
  }));
};
ws.onmessage = (e) => console.log(JSON.parse(e.data));
```

---

## Docker (Production)

```bash
# Build and start with Redis
docker-compose -f docker-compose.prod.yml up --build
```

Services:
- UAR API on `http://localhost:8000`
- Nginx reverse proxy on `http://localhost:80`
- Redis for shared rate limiting

---

## Validate the System

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=uar --cov-report=html

# Run regression tests only
pytest tests/test_regression_review.py -v
```

---

## Common Operations

### Check Health

```bash
curl http://localhost:8000/api/health/live
curl http://localhost:8000/api/health/ready
```

### View Metrics

```bash
curl http://localhost:8000/api/metrics       # Prometheus format
curl http://localhost:8000/api/metrics/json  # JSON format
```

### List Recipes

```bash
curl http://localhost:8000/api/uar/recipes
```

### Execute a Recipe

```bash
curl -X POST http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d '{
    "goal": "Review this document",
    "execution_order": [
      {"type": "recipe", "content": "review"}
    ]
  }'
```

---

## Environment Variables

| Variable | Default | Purpose |
|----------|---------|---------|
| `API_HOST` | `127.0.0.1` | Bind address |
| `API_PORT` | `8000` | Bind port |
| `PROJECT_ROOT` | `cwd` | Allowed file access root |
| `REDIS_URL` | `None` | Shared rate limiter + cache |
| `METRICS_API_KEY` | `None` | Protect `/api/metrics` in production |
| `API_KEYS` | `None` | Comma-separated `key:user:tier` |

See `.env.example` for the full list.

---

## Next Steps

- [Architecture Guide](ARCHITECTURE.md) — System design and component map
- [Onboarding Guide](../ONBOARDING.md) — Step-by-step with Ollama + Web UI
- [SLA](SLA.md) — Service objectives and monitoring setup
- [WebSocket Protocol](WEBSOCKET_PROTOCOL.md) — Event schema and streaming details
