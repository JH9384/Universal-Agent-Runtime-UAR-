# Operational Admin — Tier 3 External Tooling Guide

## Overview

UAR implements **core operational admin features natively** (Phases A–C) and defers **classic SaaS admin concerns** to external tooling (Phase D). This document maps each Tier-3 deferred item to the appropriate external tool, provides configuration pointers, and explains how UAR integrates with it.

---

## Tier 3: Deferred to External Tooling

### 1. Environment Email Settings (SMTP / Transactional Email)

**What UAR does natively:**
- Webhook alerts to Slack/Discord via `uar/api/webhook_alerts.py`
- Alert formatting via `uar/api/notifications.py`

**What is deferred:**
- SMTP server configuration
- Email templates, DKIM, SPF
- Bounce handling, unsubscribes
- Email-based alerting (PagerDuty-style)

**Recommended tooling:**
- **SendGrid**, **Mailgun**, or **Amazon SES** for transactional email
- **PagerDuty** or **Opsgenie** for on-call escalation

**Configuration:**
```bash
# In your external alerting system, point webhooks at:
# POST /api/uar/webhooks/alerts
# UAR sends structured payloads that any webhook consumer can parse.

# Example: PagerDuty integration webhook
# UAR_ALERT_WEBHOOK=https://events.pagerduty.com/integration/YOUR_KEY
```

**Files to configure:**
- `uar/api/webhook_alerts.py` — add your endpoint to `load_webhook_endpoints()`
- Environment: `UAR_ALERT_WEBHOOK`, `UAR_TRUST_WEBHOOK`

---

### 2. Domain Name / DNS Configuration

**What UAR does natively:**
- UAR is an API runtime, not a DNS provider
- CORS origins configurable via `CORS_ORIGINS`

**What is deferred:**
- Custom domain routing
- SSL/TLS certificate management
- DNS records, subdomains
- CDN configuration

**Recommended tooling:**
- **Cloudflare**, **AWS Route 53**, or **Google Cloud DNS**
- **Let's Encrypt** or **AWS ACM** for TLS

**Configuration:**
```bash
# UAR only needs to know its public origin for CORS
export CORS_ORIGINS="https://uar.your-domain.com"
```

**Files to configure:**
- `uar/config.py` — `CORS_ORIGINS`
- Reverse proxy (nginx, traefik, Caddy) in front of UAR for TLS termination

---

### 3. Authentication Policy Enforcement (SSO / MFA)

**What UAR does natively:**
- API key-based auth (`auth_middleware`)
- Tiered access (operator, developer, read-only)
- Per-skill rate limiting

**What is deferred:**
- SSO (SAML, OIDC)
- Multi-factor authentication (MFA / 2FA)
- LDAP / Active Directory integration
- Session management, OAuth flows

**Recommended tooling:**
- **Auth0**, **Okta**, **Keycloak**, or **Microsoft Entra ID**
- Place UAR behind an identity-aware proxy (e.g., **oauth2-proxy**, **pomerium**)

**Configuration:**
```bash
# UAR accepts a Bearer token in the Authorization header.
# Your SSO proxy should inject the user's API key after auth.
# Or use the proxy's forward-auth to validate tokens.

# Minimal: set a strong SECRET_KEY and rotate API keys via:
export API_KEYS="prod-key-1:admin:operator,read-key-1:viewer:read-only"
```

**Files to configure:**
- `uar/api/middleware.py` — `_load_api_keys()`, rate-limit tiers
- `uar/config.py` — `SECRET_KEY`, `API_KEYS`

---

### 4. Multiple Environment Regions / Deployment Topology

**What UAR does natively:**
- Single-node JSON/SQLite store
- PostgreSQL for multi-node shared state
- Autonomi storage for decentralized persistence

**What is deferred:**
- Multi-region replication
- Kubernetes deployment manifests
- Blue/green or canary deployments
- Load balancing across regions

**Recommended tooling:**
- **Kubernetes** + **Helm** for orchestration
- **Terraform** / **Pulumi** for infrastructure
- **ArgoCD** for GitOps deployment
- **AWS RDS** or **Google Cloud SQL** for managed PostgreSQL

**Configuration:**
```bash
# Per-region env vars
export UAR_DATABASE_URL="postgresql://uar:pass@db.us-east-1/aws.rds"
export UAR_SQLITE_PATH=""  # Clear SQLite when using Postgres
export RUNS_DIR="/data/uar/runs"
```

**Files to configure:**
- `uar/api/state.py` — store backend selection logic
- `uar/memory/postgres_store.py` — connection pooling

---

### 5. User Import & Data Deletion (GDPR / CCPA)

**What UAR does natively:**
- `DELETE /api/uar/runs/{run_id}` — delete individual runs
- `DELETE /api/uar/credentials/{id}` — delete stored credentials
- `DELETE /api/uar/maintenance/{wid}` — cancel windows

**What is deferred:**
- Bulk user data export (full GDPR SAR)
- Account deletion with cascade
- Data retention policy automation
- Anonymization / pseudonymization pipelines

**Recommended tooling:**
- **Apache Airflow** or **Temporal** for scheduled data-pipeline jobs
- **DBT** for SQL-based anonymization transforms
- Custom cron job against `list_records(user_id=...)` API

**Configuration:**
```bash
# UAR provides the primitive APIs; wire them into your compliance pipeline.
# Example: nightly anonymization job
# 1. Query /api/uar/activity?hours=168 for active users
# 2. For inactive users > 90 days, call DELETE /api/uar/runs/{run_id}
```

**Files to configure:**
- `uar/api/routers/runs.py` — `delete_run()` endpoint
- `uar/memory/base_store.py` — `RunStoreProtocol.delete()`

---

### 6. Classic Operational Admin Dashboard (SaaS-style)

**What UAR does natively:**
- `MissionControlWidget` — health, sync, plugins, credentials, maintenance, activity, data sources, updates
- All Phase A–C panels are in the React frontend

**What is deferred:**
- User management (create, invite, disable accounts)
- Role-based access control (RBAC) beyond tiered API keys
- Billing / usage metering
- Audit log archival to cold storage

**Recommended tooling:**
- **Grafana** or **Datadog** for infrastructure monitoring dashboards
- **Retool** or **Appsmith** for rapid internal CRUD admin panels
- **Apache Superset** or **Metabase** for SQL-based analytics

**Configuration:**
```bash
# Grafana can consume /api/uar/mission_control/snapshot (JSON)
# and /api/uar/health (liveness/readiness) for uptime checks.

# Retool can read/write via the operator API:
# GET  /api/uar/credentials
# POST /api/uar/maintenance?wid=...&start_at=...&end_at=...
```

**Files to reference:**
- `apps/web/src/components/MissionControlWidget.tsx` — native panels
- `uar/api/routers/health.py` — Prometheus-compatible metrics
- `uar/api/routers/mission_control.py` — snapshot endpoint

---

## Summary Table

| Capability | Native | External Tool | UAR Integration Point |
|---|---|---|---|
| Sync status & resync | ✅ `SyncStatusPanel` | — | `/api/uar/sync/*` |
| Plugin lifecycle | ✅ `PluginManager` | — | `/api/uar/plugins/*` |
| Credential vault | ✅ `CredentialVaultPanel` | HashiCorp Vault (optional) | `/api/uar/credentials/*` |
| Maintenance windows | ✅ `MaintenanceWindowPanel` | — | `/api/uar/maintenance/*` |
| Activity log | ✅ `ActivityLogPanel` | Splunk / Datadog (optional) | `/api/uar/activity` |
| File type whitelist | ✅ `FileTypeSettings` | WAF / CDN (optional) | `/api/uar/file-types` |
| Data source registry | ✅ `DataSourceRegistryPanel` | Terraform (optional) | `/api/uar/data-sources/*` |
| Self-update check | ✅ `SelfUpdatePanel` | Renovate / Dependabot | `/api/uar/update/status` |
| Email alerts | Webhooks only | SendGrid / PagerDuty | Webhook payload format |
| Domain / DNS | CORS config only | Cloudflare / Route 53 | `CORS_ORIGINS` env |
| SSO / MFA | API keys only | Auth0 / Okta / Keycloak | `Authorization: Bearer` header |
| Multi-region | Postgres/Autonomi | K8s / Terraform | `UAR_DATABASE_URL` env |
| GDPR deletion | Per-record delete | Airflow / cron | `DELETE /api/uar/runs/{id}` |
| RBAC / billing | N/A | Retool / custom | Operator API as backend |

---

## Quickstart: Hooking External Tools

### 1. Webhook Alert → PagerDuty

```bash
# Set your PagerDuty integration endpoint
export UAR_ALERT_WEBHOOK="https://events.pagerduty.com/integration/YOUR_KEY"

# UAR will POST the following JSON on trust drift, validation failure, etc.:
# {
#   "alert_type": "trust_drop",
#   "severity": "warning",
#   "message": "Trust score dropped below 0.5",
#   "timestamp": 1717600000
# }
```

### 2. Grafana Dashboard → UAR Metrics

Add a JSON API data source in Grafana pointing to:
- `http://uar:8000/api/uar/metrics` (Prometheus format)
- `http://uar:8000/api/uar/mission_control/snapshot` (JSON for health panels)

### 3. Auth0 → UAR Proxy

Deploy `oauth2-proxy` in front of UAR:
```bash
oauth2-proxy \
  --provider=oidc \
  --oidc-issuer-url=https://your-auth0-domain/ \
  --upstream=http://localhost:8000 \
  --cookie-secret=SECRET \
  --cookie-secure=true
```

UAR sees the `Authorization: Bearer <api-key>` header injected by the proxy after successful OIDC login.

---

*Last updated: Phase D complete (all Tier-3 items documented with external tooling pointers).*
