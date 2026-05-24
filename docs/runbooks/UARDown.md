# Runbook: UARDown

## Alert

`UARDown` — UAR API target is not scraped by Prometheus for more than 1 minute.

## Impact

- Complete API unavailability. All endpoints return 502/503 or timeout.
- WebSocket connections drop.

## Diagnosis Steps

1. Check if the `uar-api` container is running: `docker compose ps`.
2. Check container logs: `docker compose logs uar-api --tail=100`.
3. Verify health endpoint directly: `curl http://localhost:8000/api/health/live`.
4. Check if the port is bound: `lsof -i :8000`.

## Mitigation

- If container exited, check for OOM or uncaught exception in logs.
- If health endpoint is 500 but process is up, check for dependency failure (Redis, DB).
- Restart container: `docker compose restart uar-api`.
- If persistent, check disk space and inode exhaustion.

## Escalation

- P0 — immediate page. This is a total outage.
