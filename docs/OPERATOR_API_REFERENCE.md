# Operator API Reference

Quick reference for operators integrating with UAR Mission Control and analytics.

## Authentication

All endpoints require Bearer token authentication.

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.uar.local/api/uar/mission-control
```

Tiers: `viewer`, `operator`, `admin`.

## Core Endpoints

### Mission Control

| Endpoint | Method | Tier | Description |
|---|---|---|---|
| `/api/uar/mission-control` | GET | viewer | System snapshot |
| `/api/uar/mission-control/history` | GET | viewer | Historical snapshots |
| `/api/uar/mission-control/recommendations` | GET | viewer | Prioritized recommendations |
| `/api/uar/mission-control/alert` | GET | viewer | Top alert banner |
| `/api/uar/mission-control/operator` | GET | operator | Full operator dashboard |

### Recommendations & Trust

| Endpoint | Method | Tier | Description |
|---|---|---|---|
| `/api/uar/recommendations` | GET | viewer | All recommendations |
| `/api/uar/recommendations/trust` | GET | viewer | Trust scores |
| `/api/uar/recommendations/effectiveness` | GET | viewer | Effectiveness ranking |
| `/api/uar/recommendations/calibration` | GET | viewer | Calibration metrics |
| `/api/uar/recommendations/evidence` | GET | viewer | Evidence aggregation |
| `/api/uar/recommendations/quality` | GET | viewer | Quality metrics |
| `/api/uar/recommendations/trust/export` | GET | operator | CSV export |
| `/api/uar/recommendations/outcome` | POST | operator | Record outcome |
| `/api/uar/recommendations/outcome/bulk` | POST | admin | Bulk outcomes |
| `/api/uar/recommendations/audit` | GET | admin | Audit trail |

### Topology Analytics (Phase D)

| Endpoint | Method | Tier | Description |
|---|---|---|---|
| `/api/uar/topology/correlation` | GET | operator | Cross-run correlation |
| `/api/uar/topology/hot-paths` | GET | operator | Skill transitions |
| `/api/uar/topology/trends` | GET | operator | Historical trends |

### Replay & Burn-In

| Endpoint | Method | Tier | Description |
|---|---|---|---|
| `/api/uar/replay/{run_id}` | GET | viewer | Replay explorer |
| `/api/uar/burn-in/status` | GET | viewer | Burn-in status |
| `/api/uar/burn-in/reports` | GET | viewer | Burn-in reports |

## Webhook Alerts

Configure via `UOR_WEBHOOK_ENDPOINTS` env var (comma-separated URLs).

Alert types:
- `divergence` — confidence/trust mismatch
- `drift` — recommendation type drift
- `trust_drop` — significant score decline
- `alignment_drift` — UOR version mismatch
- `validation_failure` — artifact validation error

## CSV Export

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.uar.local/api/uar/recommendations/trust/export \
  -o trust_export.csv
```

Columns: type, trust_score, effectiveness, calibration, evidence, drift_penalty, sample_size, resolution_rate.
