# Runbook: UARRedisDisconnected

## Alert

`UARRedisDisconnected` — No Redis connected clients detected.

## Impact

- Rate limiting falls back to in-memory (per-process state), breaking multi-worker consistency.
- Metrics counters are lost on process restart.
- Cache invalidation does not propagate across workers.

## Diagnosis Steps

1. Check Redis container: `docker compose ps redis`.
2. Check Redis logs: `docker compose logs redis --tail=50`.
3. Test connectivity from uar-api: `docker compose exec uar-api redis-cli -h redis ping`.
4. Check `REDIS_URL` env var in uar-api container.

## Mitigation

- Restart Redis container if it's down.
- If network partition, restart uar-api containers to re-establish connections.
- If Redis is overloaded, scale vertically or shard by key prefix.

## Escalation

- P0 in production (breaks shared rate limiting and metrics persistence).
