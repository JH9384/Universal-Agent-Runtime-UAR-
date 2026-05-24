# Runbook: UARHealthProbeFailing

## Alert

`UARHealthProbeFailing` — External Blackbox Exporter probe of `/api/health/live` has failed for 30 seconds.

## Impact

- This is the external validation of availability. Self-reported health may still be 200, but the external network path or load balancer is failing.
- May indicate DNS, TLS, or network partition issues.

## Diagnosis Steps

1. Check Blackbox logs: `docker compose logs blackbox-exporter`.
2. Test the probe target from inside the container network: `docker compose exec blackbox-exporter wget -O- http://uar-api:8000/api/health/live`.
3. Test from the host: `curl http://localhost:8000/api/health/live`.
4. Check nginx error logs if behind a reverse proxy.

## Mitigation

- If internal network works but external doesn't, check nginx or load balancer config.
- If DNS resolution fails, verify Docker network or external DNS.
- Restart blackbox-exporter: `docker compose restart blackbox-exporter`.

## Escalation

- P0 if external probe fails for > 2 minutes (availability SLA breach).
