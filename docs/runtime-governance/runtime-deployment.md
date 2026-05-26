# Runtime Deployment Guide

## Local Runtime

```bash
bash scripts/runtime_install.sh
bash scripts/run_runtime_api.sh
```

## Docker Runtime

```bash
docker compose -f docker-compose.runtime.yml up --build
```

## Runtime API

- http://127.0.0.1:8080/health
- http://127.0.0.1:8080/telemetry
- ws://127.0.0.1:8080/ws/runtime

## Strategic Direction

This deployment guide transitions UAR into deployable operational runtime infrastructure.
