# UAR Boot and Shutdown Processes

This document describes the complete boot and shutdown processes for Universal Agent Runtime (UAR) across different deployment modes.

## Table of Contents

- [Boot Processes](#boot-processes)
  - [Local Development Boot](#local-development-boot)
  - [Docker Boot](#docker-boot)
  - [Application Lifespan](#application-lifespan)
- [Shutdown Processes](#shutdown-processes)
  - [Graceful Shutdown](#graceful-shutdown)
  - [Signal Handling](#signal-handling)
  - [Cleanup Operations](#cleanup-operations)
- [Environment Validation](#environment-validation)
- [Troubleshooting](#troubleshooting)

---

## Boot Processes

### Local Development Boot

UAR provides multiple boot scripts for local development scenarios.

#### 1. `boot.sh` - Full-Stack Boot

**Purpose:** Starts both API server and Web UI with auto-configuration

**Usage:**
```bash
./boot.sh                         # Default: API 8000, Web 5173
API_PORT=8080 WEB_PORT=3000 ./boot.sh
PYTHON=python3.11 ./boot.sh
NO_BROWSER=1 ./boot.sh            # Skip auto-open browser
```

**Boot Sequence:**
1. **Prerequisite Checks**
   - Validates Node.js and npm are installed
   - Validates Python 3.10+ is available
   - Auto-detects Python (3.11 → 3.10 → python3)

2. **Dependency Installation**
   - Installs Python dependencies: `$PYTHON -m pip install -q -e '.[dev]'`
   - Installs web dependencies (first run only): `cd apps/web && npm install --silent`

3. **API Server Startup**
   - Starts uvicorn on `127.0.0.1:$API_PORT`
   - Logs to `/tmp/uar_api.log`
   - Health check loop (40 attempts, 0.25s intervals)
   - Validates API is responding via `/api/health`

4. **Web UI Startup**
   - Starts npm dev server on `127.0.0.1:$WEB_PORT`
   - Logs to `/tmp/uar_web.log`
   - Health check loop (40 attempts, 0.5s intervals)
   - Validates web UI is responding

5. **Browser Auto-Open**
   - macOS: `open $WEB_URL`
   - Linux: `xdg-open $WEB_URL`
   - Skipped if `NO_BROWSER=1`

6. **Wait State**
   - Script waits indefinitely
   - Requires Ctrl+C to stop

**Cleanup Handler:**
```bash
cleanup() {
    echo "Shutting down..."
    kill "$WEB_PID" 2>/dev/null || true
    kill "$API_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo "Stopped."
}
trap cleanup EXIT INT TERM
```

#### 2. `start.sh` - API-Only Boot

**Purpose:** Quick startup for API-only development

**Usage:**
```bash
./start.sh                    # Default port 8000, auto-detect python
./start.sh 8080               # Custom port
./start.sh 8000 python3.11    # Specific python
```

**Boot Sequence:**
1. **Python Version Check**
   - Validates Python 3.10+
   - Auto-detects Python (3.10 → 3.11 → python3 → python3)

2. **Dependency Installation**
   - Installs Python dependencies: `$PYTHON -m pip install -q -e '.[dev]'`

3. **Quick Validation**
   - Runs pytest smoke tests: `tests/test_api.py tests/test_pipeline.py`
   - Continues even if tests fail (WARNING only)

4. **API Server Startup**
   - Starts uvicorn with `--reload` flag
   - Runs in foreground (exec)
   - Requires Ctrl+C to stop

#### 3. `scripts/quickstart.sh` - One-Command Quickstart

**Purpose:** Automated setup with Ollama integration

**Usage:**
```bash
scripts/quickstart.sh
PYTHON=python3.11 scripts/quickstart.sh
```

**Boot Sequence:**
1. **Prerequisite Checks**
   - Validates Python and npm are installed
   - Auto-detects Ollama installation

2. **Ollama Setup**
   - Checks if Ollama is running at `${OLLAMA_HOST:-http://127.0.0.1:11434}`
   - Starts Ollama in background if not running: `ollama serve`
   - Ensures model exists: `ollama pull ${OLLAMA_MODEL:-llama3.2:3b}`

3. **Dependency Installation**
   - Python: `$PYTHON -m pip install -e '.[dev]'`
   - Web: `cd apps/web && npm install`

4. **API Server Startup**
   - Starts uvicorn in background
   - Logs to `/tmp/uar-api.log`
   - Waits for API readiness (60 attempts, 1s intervals)

5. **Web UI Startup**
   - Starts npm dev server in background
   - Logs to `/tmp/uar-web.log`
   - Auto-detects port (5173-5177 range)

6. **Smoke Check**
   - Runs test request through API
   - Validates basic functionality

7. **Browser Auto-Open**
   - Opens web UI in default browser

8. **Wait State**
   - Sleeps in loop (3600s intervals)
   - Requires Ctrl+C to stop

**Cleanup Handler:**
```bash
cleanup() {
    echo "🛑 Shutting down UAR quickstart..."
    kill "${API_PID}" 2>/dev/null || true
    kill "${WEB_PID}" 2>/dev/null || true
}
trap cleanup EXIT INT TERM
```

#### 4. `scripts/first_run.sh` - First Run Wizard

**Purpose:** Guided setup for new users from zero to first result

**Usage:**
```bash
scripts/first_run.sh
PYTHON=python scripts/first_run.sh
```

**Boot Sequence:**
1. **Ollama Validation**
   - Checks Ollama is installed
   - Checks Ollama is running
   - Pulls model if needed: `ollama pull ${OLLAMA_MODEL:-llama3.2:3b}`

2. **Dependency Installation**
   - Upgrades pip
   - Installs Python dependencies: `pip install -e '.[dev]'`

3. **API Server Startup**
   - Starts uvicorn in background
   - Logs to `/tmp/uar.log`
   - Waits 2 seconds for startup

4. **First Task Execution**
   - Runs test goal: "Explain gravity simply"
   - Uses `ollama_generate` skill
   - Displays result to user

5. **Wait State**
   - Keeps API running
   - Requires Ctrl+C to stop

---

### Docker Boot

#### Dockerfile.prod

**Purpose:** Production Docker image build

**Build:**
```bash
docker build -f Dockerfile.prod -t uar:prod .
```

**Boot Sequence:**
1. **Base Image**
   - Uses `python:3.11-slim`
   - Sets environment variables for optimization

2. **User Setup**
   - Creates non-root user `uar`
   - Creates group `uar`
   - Security best practice

3. **System Dependencies**
   - Installs `curl` for health checks
   - Cleans up apt cache

4. **Python Dependencies**
   - Copies `pyproject.toml` first (layer caching)
   - Upgrades pip
   - Installs package in editable mode

5. **Entrypoint Setup**
   - Copies `scripts/docker-entrypoint.sh` to `/usr/local/bin/`
   - Makes executable

6. **Application Setup**
   - Copies application code
   - Creates directories: `/var/lib/uar/runs`, `/var/log/uar`
   - Sets ownership to `uar:uar`
   - Switches to non-root user

7. **Health Check Configuration**
   - Interval: 30s
   - Timeout: 10s
   - Start period: 40s
   - Retries: 3
   - Check: `curl -f "http://localhost:${API_PORT:-8000}/api/health"`

8. **Port Exposure**
   - Exposes port 8000 (configurable via `API_PORT`)

#### scripts/docker-entrypoint.sh

**Purpose:** Validates environment before starting application

**Boot Sequence:**
1. **Environment Validation**
   - Runs `validate_environment()` from `uar.config`
   - Runs `validate_docker_environment()` from `uar.config`
   - Checks Python version >= 3.10
   - Checks directory writability
   - Checks Docker-specific requirements (non-root user, ENVIRONMENT variable)

2. **Directory Creation**
   - Creates `/var/lib/uar/runs`
   - Creates `/var/log/uar`

3. **Permission Validation**
   - Validates `/var/lib/uar` is writable
   - Validates `/var/log/uar` is writable

4. **Application Start**
   - Executes CMD from Dockerfile
   - Typical CMD: `python -m uvicorn uar.api.server:app --host 0.0.0.0 --port ${API_PORT:-8000}`

**Run Container:**
```bash
docker run -p 8000:8000 \
  -e ENVIRONMENT=production \
  -e SECRET_KEY=your-secret-key \
  -e API_KEYS=key:user:tier \
  uar:prod
```

---

### Application Lifespan

#### FastAPI Lifespan Handler (uar/api/server.py)

**Purpose:** Application-level startup and shutdown hooks

**Implementation:**
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("UAR API starting up...")
    library = _library_dir()
    _cleanup_orphaned_temp_files(library)
    yield
    # Shutdown
    logger.info("UAR API shutting down, draining requests (5s grace period)...")
    await asyncio.sleep(SHUTDOWN_SLEEP)  # 0.1s
    logger.info("UAR API shutdown complete")
```

**Startup Operations:**
1. **Logging**
   - Logs startup message

2. **Orphaned File Cleanup**
   - Locates library directory: `_library_dir()`
   - Cleans up `.tmp` files older than 1 hour
   - Logs count of cleaned files

**Shutdown Operations:**
1. **Grace Period**
   - Waits `SHUTDOWN_SLEEP` (0.1s) for in-flight requests
   - Allows request draining

2. **Logging**
   - Logs shutdown initiation
   - Logs shutdown completion

---

## Shutdown Processes

### Graceful Shutdown

#### Signal Handling

All boot scripts implement signal handling for graceful shutdown:

**Signals Trapped:**
- `EXIT` - Normal exit
- `INT` - Ctrl+C (SIGINT)
- `TERM` - Termination signal (SIGTERM)

**Example from boot.sh:**
```bash
cleanup() {
    echo "Shutting down..."
    kill "$WEB_PID" 2>/dev/null || true
    kill "$API_PID" 2>/dev/null || true
    wait 2>/dev/null || true
    echo "Stopped."
}
trap cleanup EXIT INT TERM
```

**Example from quickstart.sh:**
```bash
cleanup() {
    echo "🛑 Shutting down UAR quickstart..."
    if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
        kill "${API_PID}" 2>/dev/null || true
    fi
    if [[ -n "${WEB_PID}" ]] && kill -0 "${WEB_PID}" 2>/dev/null; then
        kill "${WEB_PID}" 2>/dev/null || true
    fi
}
trap cleanup EXIT INT TERM
```

#### Shutdown Sequence

1. **Signal Reception**
   - Script receives EXIT, INT, or TERM signal
   - Cleanup function is triggered

2. **Process Termination**
   - Sends SIGTERM to child processes (API, Web UI)
   - Uses `kill $PID` (not `kill -9`) for graceful termination
   - Ignores errors if process already exited

3. **Wait for Completion**
   - Waits for child processes to exit
   - Timeout handled by OS default

4. **Logging**
   - Logs shutdown message
   - Logs completion

#### FastAPI Graceful Shutdown

**Uvicicorn Default Behavior:**
- Receives SIGTERM
- Stops accepting new connections
- Drains existing connections (configurable timeout)
- Shuts down application

**Custom Lifespan Shutdown:**
```python
await asyncio.sleep(SHUTDOWN_SLEEP)  # 0.1s grace period
```

**Total Grace Period:**
- Uvicicorn default: ~30s
- Custom lifespan: +0.1s
- Total: ~30.1s

---

### Cleanup Operations

#### Orphaned Temp File Cleanup

**Location:** `uar/api/server.py`, `_cleanup_orphaned_temp_files()`

**Purpose:** Clean up temporary files from previous runs

**Implementation:**
```python
def _cleanup_orphaned_temp_files(library) -> int:
    cleaned = 0
    current_time = time.time()
    max_age_seconds = 3600  # 1 hour

    for tmp_file in library.glob("*.tmp"):
        file_age = current_time - tmp_file.stat().st_mtime
        if file_age > max_age_seconds:
            tmp_file.unlink()
            cleaned += 1
    return cleaned
```

**Trigger:** Runs during FastAPI lifespan startup

**Criteria:**
- Files matching `*.tmp` pattern
- Older than 1 hour
- Located in library directory

#### Log File Cleanup

**Location:** Various boot scripts

**Log Files:**
- `/tmp/uar_api.log` - API server logs
- `/tmp/uar_web.log` - Web UI logs
- `/tmp/uar.log` - General logs
- `/tmp/uar-ollama.log` - Ollama logs

**Cleanup:** Not automatically cleaned (manual responsibility)

**Recommendation:** Add log rotation for production deployments

#### Process Cleanup

**Location:** Boot script cleanup handlers

**Operations:**
- Kill child processes (API, Web UI)
- Wait for process termination
- Ignore errors if processes already exited

---

## Environment Validation

### validate_environment()

**Location:** `uar/config.py`

**Purpose:** Validate runtime environment before startup

**Checks:**
1. **Python Version**
   - Requires Python 3.10+
   - Checks `sys.version_info >= (3, 10)`

2. **Directory Writability**
   - Checks `config.runs_dir` is writable
   - Checks `/var/lib/uar` is writable (if exists)
   - Creates test file, writes, deletes to verify

3. **Configuration Validation**
   - Calls `config.validate()`
   - Checks API port validity (1-65535)
   - Checks rate limits are positive
   - Checks max file size is positive
   - Checks production SECRET_KEY is set

### validate_docker_environment()

**Location:** `uar/config.py`

**Purpose:** Docker-specific validation

**Checks:**
1. **Docker Detection**
   - Checks for `/.dockerenv`
   - Checks `DOCKER_CONTAINER` environment variable

2. **User Validation**
   - Warns if running as root in Docker

3. **Environment Variables**
   - Requires `ENVIRONMENT` variable in Docker

**Usage:** Called by `docker-entrypoint.sh`

---

## Troubleshooting

### Boot Issues

#### API Server Fails to Start

**Symptoms:**
- Health check timeout
- "FAIL" message in boot script
- Empty log file

**Troubleshooting:**
1. Check log file: `tail -f /tmp/uar_api.log`
2. Validate Python version: `python --version`
3. Check port availability: `lsof -i :8000`
4. Validate dependencies: `python -m pip list`
5. Run validation: `python -c "from uar.config import validate_environment; print(validate_environment())"`

#### Web UI Fails to Start

**Symptoms:**
- Health check timeout
- "FAIL" message for Web UI
- Browser won't open

**Troubleshooting:**
1. Check log file: `tail -f /tmp/uar_web.log`
2. Validate npm/node: `node --version`, `npm --version`
3. Check port availability: `lsof -i :5173`
4. Install dependencies: `cd apps/web && npm install`

#### Docker Container Exits Immediately

**Symptoms:**
- Container starts and exits
- `docker logs` shows validation errors

**Troubleshooting:**
1. Check logs: `docker logs <container_id>`
2. Validate environment variables
3. Check SECRET_KEY is set in production
4. Check directory permissions: `docker exec <container_id> ls -la /var/lib/uar`

### Shutdown Issues

#### Processes Don't Stop on Ctrl+C

**Symptoms:**
- Ctrl+C doesn't stop processes
- Processes continue running

**Troubleshooting:**
1. Check for zombie processes: `ps aux | grep uvicorn`
2. Kill manually: `kill -9 <pid>`
3. Check for stuck processes in background
4. Verify signal handler is registered

#### Incomplete Cleanup

**Symptoms:**
- Temp files remain after shutdown
- Log files accumulate

**Troubleshooting:**
1. Manually clean temp files: `rm /path/to/library/*.tmp`
2. Check cleanup function execution
3. Verify cleanup handler is registered with `trap`

### Validation Issues

#### Python Version Error

**Symptoms:**
- "Python 3.10+ required"
- Boot script exits

**Solution:**
```bash
# Install Python 3.10+
brew install python@3.11  # macOS
apt install python3.11   # Ubuntu

# Or specify different Python
PYTHON=python3.11 ./boot.sh
```

#### Directory Permission Error

**Symptoms:**
- "Cannot write to directory"
- Validation fails

**Solution:**
```bash
# Fix permissions
chmod +w /var/lib/uar
chown $USER:$USER /var/lib/uar

# Or use different directory
export RUNS_DIR=./runs
./start.sh
```

#### SECRET_KEY Error in Production

**Symptoms:**
- "SECRET_KEY environment variable must be set in production"
- Container exits

**Solution:**
```bash
# Set SECRET_KEY
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")

# Or pass to Docker
docker run -e SECRET_KEY=your-secret-key uar:prod
```

---

## Best Practices

### Development

1. **Use appropriate boot script:**
   - API-only: `start.sh`
   - Full-stack: `boot.sh`
   - First-time setup: `first_run.sh`
   - Automated: `quickstart.sh`

2. **Monitor logs:**
   - API: `tail -f /tmp/uar_api.log`
   - Web: `tail -f /tmp/uar_web.log`

3. **Clean shutdown:**
   - Always use Ctrl+C for graceful shutdown
   - Avoid `kill -9` unless necessary

4. **Validate environment:**
   - Run `python -c "from uar.config import validate_environment; print(validate_environment())"`
   - Fix issues before boot

### Production

1. **Use Docker:**
   - Build with `Dockerfile.prod`
   - Use `docker-entrypoint.sh` for validation
   - Set required environment variables

2. **Configure logging:**
   - Set `LOG_FILE_PATH` for file logging
   - Ensure `/var/log/uar` is writable
   - Implement log rotation

3. **Health checks:**
   - Use `/api/health/live` for liveness
   - Use `/api/health/ready` for readiness
   - Configure appropriate intervals

4. **Graceful shutdown:**
   - Use SIGTERM for shutdown
   - Allow time for request draining
   - Monitor shutdown logs

5. **Resource cleanup:**
   - Implement log rotation
   - Clean old run records periodically
   - Monitor disk usage

---

## File Reference

| File | Purpose | Mode |
|------|---------|------|
| `boot.sh` | Full-stack boot (API + Web) | Local dev |
| `start.sh` | API-only boot | Local dev |
| `scripts/quickstart.sh` | Automated quickstart with Ollama | Local dev |
| `scripts/first_run.sh` | First-run wizard | Local dev |
| `scripts/docker-entrypoint.sh` | Docker environment validation | Docker |
| `Dockerfile.prod` | Production Docker image | Docker |
| `uar/api/server.py` | FastAPI app with lifespan handler | Application |
| `uar/config.py` | Environment validation functions | Application |

---

## Version History

- **v1.0.0** - Initial documentation
  - Documented all boot processes
  - Documented shutdown processes
  - Added troubleshooting guide
