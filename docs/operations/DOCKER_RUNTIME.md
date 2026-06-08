# Docker Runtime

D4E adds a portable Docker runtime for UAR so validation, smoke testing, and operator demos can run from a consistent capsule instead of a host-specific Python environment.

## Goals

- Keep Docker boring and repeatable.
- Preserve local development flow.
- Mount runtime state outside the container.
- Make smoke validation cheap enough to run before longer burn-in work.

## Runtime shape

```text
uar-api        FastAPI runtime on port 8000
uar-web        Optional staged web UI on port 5173
uar-dashboard  Optional operator dashboard on port 3001
redis          Optional dev Redis profile
```

Persistent host paths:

```text
./data       mounted to /data
./artifacts  mounted to /artifacts
```

## Commands

Start API only:

```bash
make docker-up
```

Start API and staged web UI:

```bash
make docker-up-full
```

Smoke-check the running API:

```bash
make docker-smoke
```

Stop containers:

```bash
make docker-down
```

## Direct Compose usage

```bash
docker compose up --build uar-api
docker compose --profile web up --build
docker compose --profile dashboard up --build
docker compose --profile redis up --build
```

## Environment knobs

```text
UAR_API_PORT          Host API port, default 8000
UAR_WEB_PORT          Host web port, default 5173
UAR_DASHBOARD_PORT    Host dashboard port, default 3001
ENVIRONMENT           development by default
CORS_ORIGINS          Browser origins allowed by the API
UAR_API_KEYS          Dev API-key map for hardened endpoints
API_KEYS              Legacy API-key map for compatibility
```

## Validation sequence

```bash
make docker-up
make docker-smoke
make docker-down
```

For D4D/D4E burn-in, use Docker smoke first, then the sliced backend validation script. Docker passing does not replace the test suite; it proves the runtime capsule boots and responds consistently.
