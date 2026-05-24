# Runbook: UARHighLatencyP99

## Alert

`UARHighLatencyP99` — UAR p99 latency is above 5 seconds for more than 3 minutes.

## Impact

- SLA breach: target p99 for `POST /api/uar/run` is < 5,000ms.
- Users experience slow responses; WebSocket clients may timeout.

## Diagnosis Steps

1. Query `histogram_quantile(0.99, rate(uar_request_duration_seconds_bucket[5m])) by (endpoint)` to find the slow endpoint.
2. Check `uar_skill_duration_seconds` for specific skill slowdowns.
3. Review `slow_request` logs for correlation IDs > 5s.
4. Check PostgreSQL slow query log if using `PostgresRunStore`.

## Mitigation

- If a specific skill is slow, check its downstream dependency (e.g., Ollama load).
- If cache miss rate is high, verify Redis connectivity.
- If PostgreSQL is the bottleneck, scale connection pool or enable read replica.

## Escalation

- P1 if p99 > 10s (breaches SLA hard limit).
