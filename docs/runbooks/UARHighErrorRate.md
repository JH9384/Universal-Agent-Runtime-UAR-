# Runbook: UARHighErrorRate

## Alert

`UARHighErrorRate` — UAR error rate is above 1% for more than 2 minutes.

## Impact

- SLA breach: target HTTP 5xx rate is < 0.1%, warning threshold is 1%.
- Users may be experiencing failed requests.
- May indicate a downstream dependency failure (Ollama, OpenAI, PostgreSQL).

## Diagnosis Steps

1. Check the `error` label on `uar_errors_total` to see which endpoints are failing.
2. Look at `/api/health/circuit-breakers` — any open circuits?
3. Review recent `slow_request` logs for correlation IDs.
4. Check downstream service health (Ollama, PostgreSQL, Redis).

## Mitigation

- If a downstream service is failing, the circuit breaker should already be open.
- If the skill cache is corrupt, POST to `/api/cache/invalidate`.
- If a specific skill is failing, temporarily disable it via feature flag.
- Scale UAR API workers if load is the cause.

## Escalation

- P1 — page on-call if error rate > 5% or duration > 10 minutes.
