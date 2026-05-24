# PagerDuty On-Call Rotation

## Setup

1. **Create a PagerDuty Service**
   - Name: `UAR Production`
   - Integration: Prometheus / Generic Events API
   - Copy the **Integration Key** (looks like `r+xxxxxxxxxxxxxxxxxxxxxx`)

2. **Set the environment variable**
   ```bash
   export PAGERDUTY_SERVICE_KEY="r+xxxxxxxxxxxxxxxxxxxxxx"
   ```
   Or add to `.env` / secrets manager and reference in `docker-compose.prod.yml`.

3. **Restart Alertmanager**
   ```bash
   docker compose restart alertmanager
   ```

## Escalation Policy

| Alert Severity | First Responder | Escalation (5 min) | Escalation (15 min) |
|---|---|---|---|
| `warning` | Primary on-call | Secondary on-call | Engineering manager |
| `critical` | Primary + Secondary | Engineering manager | CTO |

## On-Call Checklist (shift handover)

- [ ] Review open alerts in PagerDuty
- [ ] Check Grafana dashboard for anomalies
- [ ] Review `slow_request` logs from previous shift
- [ ] Verify Blackbox probe has been green for 24h
- [ ] Check Redis memory usage trending

## Runbook Quick Links

| Alert | Runbook |
|---|---|
| `UARHighErrorRate` | [UARHighErrorRate.md](UARHighErrorRate.md) |
| `UARHighLatencyP99` | [UARHighLatencyP99.md](UARHighLatencyP99.md) |
| `UARDown` | [UARDown.md](UARDown.md) |
| `UARHealthProbeFailing` | [UARHealthProbeFailing.md](UARHealthProbeFailing.md) |
| `UARTooManyWebSocketConnections` | [UARTooManyWebSocketConnections.md](UARTooManyWebSocketConnections.md) |
| `UARRedisDisconnected` | [UARRedisDisconnected.md](UARRedisDisconnected.md) |

## After-Incident Report Template

1. **Timeline** — when did the alert fire, when was it acknowledged, when was it resolved?
2. **Root Cause** — what metric or log led to the diagnosis?
3. **Mitigation** — what fixed it?
4. **Prevention** — what code or config change prevents recurrence?
