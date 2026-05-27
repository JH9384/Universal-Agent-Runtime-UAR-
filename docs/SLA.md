# UAR Service Level Agreement (SLA)

**Version:** 1.1.0  
**Effective Date:** 2026-05-24  
**Review Cycle:** Quarterly  

---

## 1. Scope

This SLA defines availability, performance, and reliability commitments for the Universal Agent Runtime (UAR) API service in production deployments. It covers:

- REST API endpoints (`/api/uar/run`, `/api/uar/stream`, `/api/uar/recipes/*`)
- WebSocket streaming endpoint (`/api/uar/stream/ws`)
- Health and metrics endpoints (`/api/health/*`, `/api/metrics`)

**Out of scope:** Skill execution quality, third-party integrations (Ollama, OpenAI, etc.), and frontend static asset serving.

---

## 2. Service Level Objectives (SLOs)

### 2.1 Availability

| Tier | Target | Measurement Window | Penalty Threshold |
|------|--------|-------------------|-------------------|
| **Core API** | 99.9% | Rolling 30 days | < 99.5% triggers review |
| **Health Probes** | 99.95% | Rolling 30 days | < 99.9% triggers escalation |
| **Metrics** | 99.0% | Rolling 30 days | Best effort; no penalty |

**Calculation:**
```
availability = (total minutes - downtime minutes) / total minutes
```

Downtime = any minute where `/api/health/live` returns non-200 or times out > 5s.

### 2.2 Latency

| Endpoint | p50 | p99 | Measurement |
|----------|-----|-----|-------------|
| `POST /api/uar/run` | < 500ms | < 5,000ms | Time to first byte (TTFB) |
| `GET /api/uar/stream` (HTTP) | < 200ms | < 500ms | Time to first event |
| `WS /api/uar/stream/ws` | < 100ms | < 500ms | Time to first event |
| `GET /api/health/live` | < 10ms | < 50ms | Response time |
| `GET /api/health/ready` | < 50ms | < 200ms | Response time (Ollama check runs in thread pool, non-blocking) |

**Exclusions:** Skill execution time is excluded from API latency; only framework overhead (auth, rate limiting, request parsing, response serialization) is measured.

### 2.3 Error Rate

| Metric | Target | Window |
|--------|--------|--------|
| HTTP 5xx rate | < 0.1% | Rolling 24 hours |
| HTTP 4xx rate | < 1.0% | Rolling 24 hours |
| WebSocket disconnect (error) | < 0.5% | Rolling 24 hours |

### 2.4 Throughput

| Metric | Target | Notes |
|--------|--------|-------|
| Concurrent connections | 1,000 | WebSocket + HTTP combined |
| Requests per second | 500 | Sustained for 5 minutes |
| Max execution order depth | 50 | Skills + recipes in single request |

---

## 3. Current State vs. Target

### 3.1 What We Have

| Capability | Status | Evidence |
|------------|--------|----------|
| Basic metrics collection | ✅ | `MetricsCollector` in `uar/api/metrics.py` |
| Histogram / percentile tracking | ✅ | `Histogram` class with p50/p99 buckets |
| Prometheus exposition format | ✅ | `get_prometheus_format()` |
| Skill-level latency breakdown | ✅ | `record_skill()` wired into executor |
| Liveness probe | ✅ | `GET /api/health/live` |
| Readiness probe | ✅ | `GET /api/health/ready` |
| Circuit breaker health | ✅ | `GET /api/health/circuit-breakers` |
| Error tracking | ✅ | Per-endpoint error counts |
| Request counting | ✅ | Per-endpoint request counts |
| Uptime tracking | ✅ | `uptime_seconds` in metrics |

### 3.2 What's Missing for Full SLA Compliance

| Gap | Impact on SLA | Priority | Owner |
|-----|---------------|----------|-------|
| ~~No histograms / percentile tracking~~ | ~~Cannot measure p99 latency~~ | ~~**Critical**~~ | ✅ Completed — `Histogram` class with p50/p99 in `uar/api/metrics.py` |
| No external metrics persistence | Metrics lost on restart | **High** | Backend |
| No synthetic probing | Availability is self-reported | **High** | SRE |
| No alert wiring | Cannot enforce MTTD/MTTR | **High** | SRE |
| ~~Redis rate limiter not default~~ | ~~Breaks multi-worker accuracy~~ | ~~**Medium**~~ | ✅ Completed — `create_rate_limiter()` auto-selects `RedisRateLimiter` when `REDIS_URL` is set |
| ~~No request duration logging~~ | ~~Hard to debug latency spikes~~ | ~~**Medium**~~ | ✅ Completed — HTTP middleware `metrics_middleware` records every endpoint in `uar/api/server.py` |
| ~~No skill-level latency breakdown~~ | ~~Cannot attribute slowdowns~~ | ~~**Medium**~~ | ✅ Completed — `record_skill()` wired into `uar/core/executor.py` |
| ~~No WebSocket connection tracking~~ | ~~Cannot validate 1,000 conn target~~ | ~~**Medium**~~ | ✅ Completed — `uar_websocket_connections` gauge exposed via `_WebSocketConnectionCounter` |

---

## 4. Measurement Infrastructure

### 4.1 Required Metrics

These metrics must be collected and retained for 90 days to validate SLA compliance:

```
# Availability
uar_uptime_ratio           # gauge, 0-1
uar_health_check_failures_total  # counter

# Latency (histograms with buckets: 10ms, 50ms, 100ms, 250ms, 500ms, 1s, 2s, 5s, 10s)
uar_request_duration_seconds{endpoint, method}  # histogram
uar_skill_duration_seconds{skill_name}          # histogram

# Error rate
uar_requests_total{endpoint, status_code}       # counter
uar_errors_total{endpoint, error_type}          # counter

# Throughput
uar_active_connections      # gauge
uar_websocket_connections   # gauge
```

### 4.2 Recommended Stack

| Layer | Tool | Purpose |
|-------|------|---------|
| Instrumentation | `prometheus-fastapi-instrumentator` | Automatic HTTP metric collection |
| Aggregation | Prometheus | Time-series storage and querying |
| Visualization | Grafana | Dashboards for SLO tracking |
| Alerting | Alertmanager | PagerDuty/Slack escalation |
| Synthetic probes | Blackbox Exporter | External availability validation |
| Log aggregation | Loki or ELK | Correlation with metric spikes |

---

## 5. Incident Response

### 5.1 Severity Definitions

| Severity | Criteria | Response Time | Resolution Target |
|----------|----------|---------------|-------------------|
| **P0** | API completely unavailable (> 1 min) | 5 min | 30 min |
| **P1** | p99 latency > 10s OR error rate > 1% | 15 min | 2 hours |
| **P2** | p99 latency > 5s OR error rate > 0.5% | 30 min | 4 hours |
| **P3** | Metrics missing, non-critical degredation | 2 hours | 24 hours |

### 5.2 MTTD / MTTR Targets

| Metric | Target | Current |
|--------|--------|---------|
| Mean Time To Detect (MTTD) | < 2 minutes | Manual log inspection |
| Mean Time To Respond (MTTR) | < 30 minutes | N/A |
| Mean Time To Resolve (MTTR) | P0: 30 min, P1: 2 hr | N/A |

---

## 6. SLA Compliance Checklist

Before claiming SLA compliance, verify:

- [ ] Prometheus scraping endpoint (`/api/metrics`) returns valid exposition format
- [ ] Grafana dashboard shows availability, p50/p99 latency, error rate panels
- [ ] Alertmanager rules fire on P0/P1/P2 thresholds
- [ ] Blackbox exporter probes `/api/health/live` from external network
- [ ] `docker-compose.prod.yml` includes Prometheus + Grafana services
- [ ] Runbook exists for each alert rule
- [ ] On-call rotation is configured
- [ ] Quarterly SLA review meeting is scheduled

---

## 7. Gaps & Recommended Actions

### Immediate (This Sprint) — Completed ✅

1. ~~**Add histogram support to `MetricsCollector`**~~ ✅ Completed 2026-05-22
   - File: `uar/api/metrics.py`
   - Added `Histogram` class with configurable buckets, `percentile()` method, and Prometheus-format export
   - `uar_request_duration_seconds_bucket` and `uar_skill_duration_seconds_bucket` visible in `/api/metrics`

2. ~~**Instrument all endpoints with automatic timing**~~ ✅ Completed 2026-05-24
   - File: `uar/api/server.py`
   - Added `metrics_middleware` HTTP middleware that records every request path + duration
   - Acceptance: Every endpoint appears in metrics with count + duration

### Short-term (Next 2 Sprints)

3. ~~**Add Redis rate limiter as production default**~~ ✅ Completed 2026-05-22
   - File: `uar/api/middleware.py`
   - `create_rate_limiter()` returns `RedisRateLimiter` when `REDIS_URL` is set; raises in production if missing
   - Acceptance: Load test with 4 workers shows shared rate limit state

4. ~~**Add skill-level execution latency**~~ ✅ Completed 2026-05-22
   - File: `uar/core/executor.py`
   - `record_skill()` called at success, retry, and failure paths with duration and error flag
   - `uar_skill_duration_seconds` shows per-skill p50/p99 in `/api/metrics/json`

5. **Add request duration logging**
   - File: `uar/api/server.py`
   - Action: Log slow requests (> p99 threshold) with path, duration, and correlation ID
   - Acceptance: Latency spikes are identifiable from logs without metrics

### Medium-term (Next Quarter)

6. **Deploy Prometheus + Grafana stack**
   - File: `docker-compose.prod.yml`, new `observability/` directory
   - Action: Add Prometheus, Grafana, and Alertmanager to production compose
   - Acceptance: Dashboards load with real data within 5 minutes of startup

7. **Add synthetic health probing**
   - File: New `observability/blackbox.yml`
   - Action: Blackbox Exporter probes `/api/health/live` every 10s
   - Acceptance: Alert fires when probe fails 3 times in a row

---

## 8. Sign-off

| Role | Name | Date |
|------|------|------|
| Engineering Lead | | |
| SRE / Platform | | |
| Product Manager | | |

---

*This SLA is a living document. Review quarterly and update targets based on operational data.*
