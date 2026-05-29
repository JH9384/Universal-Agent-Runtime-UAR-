# UAR Boot Sequence

This document provides a detailed step-by-step boot sequence for the Universal Agent Runtime (UAR) system, including UOR integration points.

## Overview

The UAR boot sequence varies based on the deployment mode:
- **Local Development**: `boot.sh`, `start.sh`, `quickstart.sh`, `first_run.sh`, plus Makefile targets (`make up`, `make up-full`, `make api`)
- **Docker**: `docker-entrypoint.sh` with `Dockerfile.prod`

## Full-Stack Boot Sequence (boot.sh)

### Phase 1: Initialization

```
┌─────────────────────────────────────────────────────────┐
│ 1. Script Startup                                     │
│    - Set working directory to project root           │
│    - Parse environment variables:                    │
│      * API_PORT (default: 8000)                       │
│      * WEB_PORT (default: 5173)                       │
│      * PYTHON (auto-detect: 3.11 → 3.10 → python3)    │
│      * NO_BROWSER (skip auto-open if set)             │
└─────────────────────────────────────────────────────────┘
```

### Phase 2: Prerequisite Validation

```
┌─────────────────────────────────────────────────────────┐
│ 2. Prerequisite Checks                                 │
│    ✓ Check node is installed                           │
│    ✓ Check npm is installed                            │
│    ✓ Check Python 3.10+ is available                  │
│    ✗ Exit on failure                                  │
└─────────────────────────────────────────────────────────┘
```

### Phase 3: Dependency Installation

```
┌─────────────────────────────────────────────────────────┐
│ 3. Python Dependencies                                 │
│    $PYTHON -m pip install -q -e '.[dev]'               │
│    - Installs all Python packages from pyproject.toml  │
│    - Includes UOR integration modules                  │
│    - Includes UOR Foundation assets (Sigmatics, etc.)   │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Web Dependencies (first run only)                   │
│    cd apps/web && npm install --silent                │
│    - Installs React/Vite dependencies                 │
│    - Only runs if node_modules doesn't exist          │
└─────────────────────────────────────────────────────────┘
```

### Phase 4: API Server Startup

```
┌─────────────────────────────────────────────────────────┐
│ 5. API Server Launch                                   │
│    $PYTHON -m uvicorn uar.api.server:app              │
│      --host 127.0.0.1 --port $API_PORT               │
│      > /tmp/uar_api.log 2>&1 &                        │
│    - Starts FastAPI server in background               │
│    - Logs to /tmp/uar_api.log                          │
│    - Stores API_PID for cleanup                       │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 6. API Health Check (40 attempts, 0.25s intervals)     │
│    for i in $(seq 1 40):                              │
│      if curl -fs $API_URL/api/health; then             │
│        break                                           │
│      fi                                               │
│      sleep 0.25                                      │
│    done                                               │
│    - Validates /api/health endpoint is responding       │
│    - Checks API_PID is still running                   │
│    ✗ Exit on timeout or process death                 │
└─────────────────────────────────────────────────────────┘
```

**API Server Internal Boot (FastAPI Lifespan)**

```
┌─────────────────────────────────────────────────────────┐
│ FastAPI Lifespan Startup Hook                          │
│                                                         │
│ 1. Logger Initialization                               │
│    - "UAR API starting up..."                          │
│                                                         │
│ 2. Orphaned Temp File Cleanup                          │
│    - _cleanup_orphaned_temp_files(library)            │
│    - Removes *.tmp files older than 1 hour             │
│    - Logs count of cleaned files                       │
│                                                         │
│ 3. UOR Runtime Seeding (non-fatal)                     │
│    - seed_standard_runtimes(get_default_store())      │
│    - Idempotent — safe to run on every startup         │
│                                                         │
│ 4. External Skill Plugin Loading (non-fatal)          │
│    - load_plugins() scans ~/.uar/skills/ and PyPI     │
│    - entry points for uar.skills                      │
│                                                         │
│ 5. Production Security Checks                          │
│    - Warns if CORS_ORIGINS not set in production        │
│    - Warns if SECURITY_HEADERS not enabled              │
│                                                         │
│ 6. OpenTelemetry Tracing Initialization              │
│    - setup_fastapi_tracing(app)                        │
│    - No-op if OTEL not configured                      │
│                                                         │
│ 7. Environment Validation (fail-fast)                │
│    - validate_environment()                            │
│    - validate_docker_environment()                     │
│    - Raises RuntimeError on any issue                  │
│                                                         │
│ 8. Advanced Integration Config Validation (non-fatal) │
│    - Neo4j, OpenAI, etc.                               │
│    - Results logged, startup continues                 │
│                                                         │
│ 9. Background Retention Purge Task                     │
│    - _retention_purge_loop()                         │
│    - Only if run_retention_days > 0                    │
│    - Checks hourly and purges old records              │
└─────────────────────────────────────────────────────────┘
```

### Phase 5: Web UI Startup

```
┌─────────────────────────────────────────────────────────┐
│ 7. Web UI Launch                                       │
│    (cd apps/web && npm run dev                          │
│      --port $WEB_PORT --host 127.0.0.1)                │
│      > /tmp/uar_web.log 2>&1 &                         │
│    - Starts Vite dev server in background               │
│    - Logs to /tmp/uar_web.log                          │
│    - Stores WEB_PID for cleanup                        │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 8. Web Health Check (40 attempts, 0.5s intervals)      │
│    for i in $(seq 1 40):                              │
│      if curl -fs $WEB_URL; then                        │
│        break                                           │
│      fi                                               │
│      sleep 0.5                                        │
│    done                                               │
│    - Validates web UI is responding                    │
│    - Checks WEB_PID is still running                    │
│    ✗ Exit on timeout or process death                 │
└─────────────────────────────────────────────────────────┘
```

### Phase 6: Browser Auto-Open

```
┌─────────────────────────────────────────────────────────┐
│ 9. Browser Auto-Open (if NO_BROWSER not set)          │
│    macOS: open $WEB_URL                              │
│    Linux: xdg-open $WEB_URL                           │
│    - Opens web UI in default browser                   │
└─────────────────────────────────────────────────────────┘
```

### Phase 7: Ready State

```
┌─────────────────────────────────────────────────────────┐
│ 10. Ready State                                        │
│    ┌───────────────────────────────────────────────┐  │
│    │  UAR is running                               │  │
│    │    Web UI:   http://localhost:5173           │  │
│    │    API:      http://127.0.0.1:8000           │  │
│    │    Health:   http://127.0.0.1:8000/api/health │  │
│    │    Logs:     tail -f /tmp/uar_api.log        │  │
│    │              tail -f /tmp/uar_web.log          │  │
│    │                                             │  │
│    │  Press Ctrl+C to stop both.                  │  │
│    └───────────────────────────────────────────────┘  │
│                                                         │
│ 11. Wait State                                        │
│    wait # Waits indefinitely for either process       │
└─────────────────────────────────────────────────────────┘
```

## API-Only Boot Sequence (start.sh)

### Phase 1: Python Detection

```
┌─────────────────────────────────────────────────────────┐
│ 1. Python Version Check                                │
│    - Auto-detects Python: 3.10 → 3.11 → python3 → python3 │
│    - Validates Python 3.10+                            │
│    ✗ Exit on failure                                  │
└─────────────────────────────────────────────────────────┘
```

### Phase 2: Dependency Installation

```
┌─────────────────────────────────────────────────────────┐
│ 2. Python Dependencies                                 │
│    $PYTHON -m pip install -q -e '.[dev]'               │
│    - Installs all Python packages                       │
│    - Includes UOR integration modules                  │
└─────────────────────────────────────────────────────────┘
```

### Phase 3: Quick Validation

```
┌─────────────────────────────────────────────────────────┐
│ 3. Smoke Tests                                          │
│    pytest tests/test_api.py tests/test_pipeline.py     │
│    - Continues even if tests fail (WARNING only)       │
└─────────────────────────────────────────────────────────┘
```

### Phase 4: API Server Startup

```
┌─────────────────────────────────────────────────────────┐
│ 4. API Server Launch (Foreground)                      │
│    $PYTHON -m uvicorn uar.api.server:app              │
│      --host 127.0.0.1 --port $PORT --reload           │
│    - Starts in foreground with auto-reload             │
│    - Runs FastAPI lifespan startup hook                │
│    - Requires Ctrl+C to stop                           │
└─────────────────────────────────────────────────────────┘
```

## Docker Boot Sequence

### Phase 1: Docker Image Build (Dockerfile.prod)

```
┌─────────────────────────────────────────────────────────┐
│ 1. Base Image                                          │
│    FROM python:3.11-slim                               │
│    - Sets PYTHONUNBUFFERED=1                           │
│    - Sets PYTHONDONTWRITEBYTECODE=1                   │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 2. User Setup                                          │
│    RUN groupadd -r uar && useradd -r -g uar uar       │
│    - Creates non-root user for security                 │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 3. System Dependencies                                 │
│    RUN apt-get update && apt-get install -y curl     │
│    - Installs curl for health checks                   │
│    RUN rm -rf /var/lib/apt/lists/*                     │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Python Dependencies (Layer Caching)                │
│    COPY pyproject.toml .                              │
│    RUN pip install --no-cache-dir -e .                │
│    - Installs UOR integration modules                  │
│    - Installs UOR Foundation assets                   │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 5. Entrypoint Setup                                    │
│    COPY scripts/docker-entrypoint.sh /usr/local/bin/   │
│    RUN chmod +x /usr/local/bin/docker-entrypoint.sh    │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 6. Application Setup                                    │
│    COPY . /app                                         │
│    RUN mkdir -p /var/lib/uar/runs /var/log/uar         │
│    RUN chown -R uar:uar /app /var/lib/uar /var/log/uar │
│    USER uar                                            │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 7. Health Check Configuration                           │
│    HEALTHCHECK --interval=30s --timeout=10s           │
│      --start-period=40s --retries=3                   │
│      CMD curl -f "http://localhost:8000/api/health"   │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 8. Port Exposure                                       │
│    EXPOSE 8000                                         │
└─────────────────────────────────────────────────────────┘
```

### Phase 2: Docker Container Startup (docker-entrypoint.sh)

```
┌─────────────────────────────────────────────────────────┐
│ 1. Environment Validation                             │
│    python -c "from uar.config import (                  │
│      validate_environment,                              │
│      validate_docker_environment                       │
│    ); validate_environment();                          │
│      validate_docker_environment()"                     │
│    - Validates Python version >= 3.10                 │
│    - Validates directory writability                  │
│    - Validates Docker-specific requirements            │
│    ✗ Exit on validation failure                       │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 2. Directory Creation                                 │
│    mkdir -p /var/lib/uar/runs /var/log/uar             │
│    - Creates required directories                     │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 3. Permission Validation                               │
│    - Validates /var/lib/uar is writable                │
│    - Validates /var/log/uar is writable                 │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ 4. Application Start                                   │
│    exec python -m uvicorn uar.api.server:app           │
│      --host 0.0.0.0 --port ${API_PORT:-8000}          │
│    - Runs FastAPI lifespan startup hook                │
│    - Seeds UOR standard runtimes                       │
│    - Loads external skill plugins                      │
└─────────────────────────────────────────────────────────┘
```

## UOR Integration Points in Boot Sequence

### UOR Runtime Seeding

**Location**: FastAPI lifespan startup hook in `uar/api/lifespan.py`

**Timing**: During API server startup, before accepting requests

**Operations**:
1. `seed_standard_runtimes(get_default_store())` is called
2. Seeds canonical UOR object/runtime records into the SQLite-backed object store
3. Operation is idempotent — safe to run on every startup
4. Non-fatal: if seeding fails, a warning is logged and startup continues

**Code**:
```python
from uar.objects import get_default_store, seed_standard_runtimes

seed_standard_runtimes(get_default_store())
```

### UOR Integration in System Components

**Skill Registry**:
- Computes skill digests during execution (not at boot)
- Uses UOR wrap_input_data for skill source code
- Stores digests for identity verification in event records

**Cache Layer**:
- JsonRunStore persists records with UOR digests when UOR is enabled

**API Layer**:
- Wraps request/response data with UOR objects
- Logs digests for verification in run events

## Graceful Shutdown Sequence

### Signal Handling

```
┌─────────────────────────────────────────────────────────┐
│ Signal Reception (EXIT, INT, TERM)                     │
│    - Script receives signal                             │
│    - Cleanup function triggered via trap               │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ Process Termination                                    │
│    kill "$WEB_PID" 2>/dev/null || true                 │
│    kill "$API_PID" 2>/dev/null || true                 │
│    - Sends SIGTERM to child processes                  │
│    - Ignores errors if process already exited          │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ Wait for Completion                                    │
│    wait 2>/dev/null || true                             │
│    - Waits for child processes to exit                 │
└─────────────────────────────────────────────────────────┘
         ↓
┌─────────────────────────────────────────────────────────┐
│ Logging                                                │
│    echo "Shutting down..."                            │
│    echo "Stopped."                                     │
└─────────────────────────────────────────────────────────┘
```

### FastAPI Graceful Shutdown

```
┌─────────────────────────────────────────────────────────┐
│ FastAPI Lifespan Shutdown Hook                         │
│                                                         │
│ 1. Cancel Background Tasks                             │
│    - Cancel retention purge loop                     │
│    - Wait for cancellation to complete                 │
│                                                         │
│ 2. Request Draining                                    │
│    - Uvicorn stops accepting new connections           │
│    - Drains WebSocket connections with active wait     │
│                                                         │
│ 3. Configurable Grace Period                           │
│    - SHUTDOWN_SLEEP defaults to 30s                  │
│    - Override via SHUTDOWN_GRACE_SECONDS env var      │
│    - Polls active WebSocket count every 1s            │
│                                                         │
│ 4. Logging                                              │
│    - "UAR API shutting down, draining active ..."   │
│    - "All connections drained cleanly" or grace expiry │
│                                                         │
│ 5. Resource Cleanup                                     │
│    - Metrics collector shutdown                        │
│    - Postgres connection pool close                    │
│    - Per-domain aiohttp sessions close                 │
│    - "UAR API shutdown complete"                       │
└─────────────────────────────────────────────────────────┘
```

## Environment Variables

### Boot Script Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_PORT` | 8000 | API server port |
| `WEB_PORT` | 5173 | Web UI port |
| `PYTHON` | auto-detected | Python executable path |
| `NO_BROWSER` | unset | Skip browser auto-open if set |

### Application Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | 127.0.0.1 | Bind address |
| `API_PORT` | 8000 | Listen port |
| `SECRET_KEY` | generated | JWT / session secret |
| `API_KEYS` | dev_key:dev:admin | Comma-separated `key:user:tier` |
| `DEBUG` | false | Enable debug mode |
| `ENVIRONMENT` | development | `production` tightens CORS + disables debug |
| `LOG_LEVEL` | info | Uvicorn / app log level |
| `CORS_ORIGINS` | localhost:3000,5173 | Comma-separated allowed origins |
| `RATE_LIMIT_ENABLED` | true | Toggle sliding-window rate limiter |
| `RUNS_DIR` | runs | Run record storage directory |
| `UAR_DATABASE_URL` | unset | Postgres URL — activates `PostgresRunStore` |
| `REDIS_URL` | unset | Enables distributed rate limiting |
| `OLLAMA_HOST` | http://127.0.0.1:11434 | Ollama endpoint |
| `OLLAMA_MODEL` | llama3.2:3b | Default Ollama model |
| `SHUTDOWN_GRACE_SECONDS` | 30 | Grace period for connection drain |
| `UAR_SKILL_CACHE_TTL` | 300 | Skill compilation cache TTL (seconds) |
| `UAR_GC_THRESHOLD` | 50 | GC hint after runs with N+ events |
| `UAR_CONTEXT_DISK_OVERFLOW` | false | Spill `PipelineContext` events to disk |
| `UAR_HIERARCHICAL_EXECUTION` | false | Recipe nested-execution mode |
| `BACKPRESSURE_ENABLED` | true | Adaptive SSE backpressure |
| `METRICS_ENABLED` | true | Enable metrics collection |
| `METRICS_PORT` | 9090 | Prometheus metrics port |
| `UAR_ENABLE_UOR_EXTENSIONS` | false | Enable optional UOR extensions |
| `UOR_DB_PATH` | uar.sqlite3 | UOR object store path |
| `LOG_FILE_PATH` | /var/log/uar/app.log | Production log file path |
| `SECURITY_HEADERS` | unset | Set to `enabled` for security headers |
| `UAR_GZIP_MIN_SIZE` | 1024 | Minimum response size for GZip (bytes) |

### Docker Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ENVIRONMENT` | Yes (Docker) | Environment name (development/production) |
| `SECRET_KEY` | Yes (production) | Secret key for production |
| `API_KEYS` | Yes (production) | API keys in format: key:user:tier,key2:user2:tier2 |
| `API_PORT` | 8000 | API server port |
| `RUNS_DIR` | /var/lib/uar/runs | Directory for run records |
| `LOG_FILE_PATH` | /var/log/uar | Directory for logs |

## Log Files

### Boot Script Logs

| File | Content | Purpose |
|------|---------|---------|
| `/tmp/uar_api.log` | API server stdout/stderr | API server debugging |
| `/tmp/uar_web.log` | Web UI stdout/stderr | Web UI debugging |
| `/tmp/uar.log` | General logs | Quickstart/first_run logs |
| `/tmp/uar-ollama.log` | Ollama logs | Ollama service logs |

### Application Logs

| Location | Content | Purpose |
|----------|---------|---------|
| `runs/uar_runs.jsonl` | Run records with UOR digests | Persistent run storage |
| Configured via `LOG_FILE_PATH` | Application logs | File-based logging |

## Troubleshooting Boot Issues

### API Server Timeout

**Symptoms**: Health check timeout after 10 seconds

**Checklist**:
1. View logs: `tail -f /tmp/uar_api.log`
2. Check Python version: `python --version`
3. Check port availability: `lsof -i :8000`
4. Validate dependencies: `python -m pip list`
5. Run validation: `python -c "from uar.config import validate_environment; print(validate_environment())"`

### Web UI Timeout

**Symptoms**: Health check timeout after 20 seconds

**Checklist**:
1. View logs: `tail -f /tmp/uar_web.log`
2. Check Node/npm: `node --version`, `npm --version`
3. Check port availability: `lsof -i :5173`
4. Install dependencies: `cd apps/web && npm install`

### Docker Container Exit

**Symptoms**: Container starts and exits immediately

**Checklist**:
1. View logs: `docker logs <container_id>`
2. Validate environment variables
3. Check SECRET_KEY is set in production
4. Check directory permissions: `docker exec <container_id> ls -la /var/lib/uar`

### UOR Integration Issues

**Symptoms**: Errors related to UOR modules

**Checklist**:
1. Verify UOR runtime seeding works: `python -c "from uar.objects import seed_standard_runtimes, get_default_store; seed_standard_runtimes(get_default_store())"`
2. Check for import errors in logs
3. Verify UOR extensions are enabled if needed: `UAR_ENABLE_UOR_EXTENSIONS=true`
4. Check `UOR_DB_PATH` is writable (default: `uar.sqlite3`)

## Boot Sequence Flowchart

```
START
  ↓
[Parse Environment Variables]
  ↓
[Validate Prerequisites]
  ↓ (fail)
[Install Dependencies] → EXIT
  ↓
[Start API Server]
  ↓
[API Health Check] → (fail) → EXIT
  ↓
[FastAPI Lifespan Startup]
  ├─ [Orphaned Temp Cleanup]
  ├─ [UOR Runtime Seeding]
  ├─ [External Plugin Loading]
  ├─ [Production Security Checks]
  ├─ [OpenTelemetry Tracing Setup]
  ├─ [Environment Validation]
  ├─ [Advanced Config Validation]
  └─ [Background Retention Purge]
  ↓
[Start Web UI] (if full-stack)
  ↓
[Web Health Check] → (fail) → EXIT
  ↓
[Auto-open Browser] (if not skipped)
  ↓
[READY STATE]
  ↓
[Wait for Signal]
  ↓ (EXIT, INT, TERM)
[Graceful Shutdown]
  ├─ [Terminate Processes]
  ├─ [FastAPI Lifespan Shutdown]
  └─ [Cleanup]
  ↓
END
```

## Latest Boot Capture (May 29, 2026)

### Startup Command

```bash
cd /Volumes/Sabrent\ SSD/Projects/Universal-Agent-Runtime-UAR-
python -m uvicorn uar.api.server:app --host 127.0.0.1 --port 8000
```

### Boot Log (abbreviated)

```text
INFO:     Started server process [73490]
INFO:     Waiting for application startup.
2026-05-29 06:04:00,000 - uar.api.server - INFO - Booting UAR 1.1.0 (aligned with UOR v0.5.2)
2026-05-29 06:04:00,200 - uar.core.recipes - INFO - All recipe skills validated successfully
2026-05-29 06:04:00,300 - uar.api.lifespan - INFO - UAR API starting up...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### Health Check Results

| Endpoint | Status | Response |
|---|---|---|
| `GET /api/health` | 200 | `{"status":"healthy","version":"1.1.0","uor_upstream_version":"v0.5.2"}` |
| `GET /api/health/live` | 200 | `{"status":"alive"}` |
| `GET /api/health/ready` | 200 | `{"status":"ready","checks":{"skills_loaded":true,"disk_writable":true,"ollama_reachable":true,"circuit_breakers":true,"open_circuits":[]}}` |
| `GET /api/health/circuit-breakers` | 200 | All circuits `closed` (openai, lm_studio, anthropic, gemini, mistral, groq) |
| `GET /api/metrics/json` | 200 | `{"uptime_seconds":9.81,"total_requests":6,"total_errors":0.0,"endpoints":{...}}` |
| `GET /api/uar/skills` | 200 | 127 registered skills |
| `GET /api/uar/recipes` | 200 | 11 built-in recipes |

### Running Process

```bash
$ lsof -ti:8000
73490
```

### Known Boot Notes

- **Optional dependency warnings**: `unstructured` and `docling` warnings are expected on lean installs — they are optional heavy dependencies for enhanced document ingestion.
- **Recipe warnings**: Several default recipes reference optional skills (graphrag, autonomi, uor ecosystem) that return graceful errors when optional dependencies are absent. This is expected and non-fatal.

## Related Documentation

- [BOOT_CAPTURE.md](./BOOT_CAPTURE.md) - Live boot log with endpoint reference
- [BOOT_AND_SHUTDOWN.md](./BOOT_AND_SHUTDOWN.md) - Legacy boot and shutdown documentation (see BOOT_SEQUENCE.md for current info)
- [UOR_INTEGRATION_GUIDE.md](../uar/core/UOR_INTEGRATION_GUIDE.md) - UOR integration documentation
