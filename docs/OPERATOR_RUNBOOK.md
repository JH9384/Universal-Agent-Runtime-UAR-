# Operator Runbook

Operational procedures for running UAR in production.

## Daily Checklist

1. **Mission Control Overview**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.uar.local/api/uar/mission-control
   ```
   - Check `system_health.status` is "healthy"
   - Review `trust_summary.top_trusted` and `trust_summary.drift_count`
   - If `drift_count > 0`, investigate `/api/uar/recommendations/trust`

2. **Alert Banner**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.uar.local/api/uar/mission-control/alert
   ```
   - Address any `severity: "critical"` alerts immediately
   - `severity: "warning"` alerts should be triaged within 4 hours

3. **Recommendations**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.uar.local/api/uar/mission-control/recommendations
   ```
   - Export CSV weekly for stakeholder review
   - Record outcomes for any acted-upon recommendations

## Weekly Checklist

1. **Trust Validation**
   ```bash
   python scripts/hardening/trust_validation.py
   ```
   - Verify trust distribution is not compressed
   - Check Spearman correlation >= 0.3
   - Review divergence cases

2. **Topology Analytics**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.uar.local/api/uar/topology/correlation?hours=168
   ```
   - Identify goals with high failure rates
   - Check for shared skill patterns in failing goals

3. **Burn-In Status**
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.uar.local/api/uar/burn-in/status
   ```
   - Ensure burn-in is running or completed within last 7 days
   - Review latest report for anomalies

## Recording Outcomes

When a recommendation is acted upon, record the result:

```bash
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"recommendation_id":"rec-abc","outcome_type":"resolved"}' \
  https://api.uar.local/api/uar/recommendations/outcome
```

Types: `resolved`, `recurred`, `unknown`

## Investigating Divergence

When webhook alerts fire for divergence:

1. Query recommendations to see mismatch:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     https://api.uar.local/api/uar/recommendations?hours=24
   ```

2. Look for:
   - `confidence > 0.90` and `trust_score < 0.40`: High confidence, poor track record
   - `confidence < 0.50` and `trust_score > 0.80`: Low confidence, strong track record

3. For high-confidence/low-trust cases:
   - Check if recommendation type is new (low sample size)
   - Verify outcome attribution is correct
   - Consider if environment changed (new release, topology shift)

## Investigating Drift

When `drift_penalty > 0` on a recommendation type:

1. Query the audit log:
   ```bash
   curl -H "Authorization: Bearer $TOKEN" \
     "https://api.uar.local/api/uar/recommendations/audit?recommendation_id=REC_ID"
   ```

2. Check for:
   - Recent `outcome:recurred` events (negative signal)
   - Declining `outcome:resolved` rate
   - Environmental changes coinciding with drift onset

3. If drift is persistent:
   - Extend burn-in duration
   - Increase `evidence_component` weight
   - Review if recommendation logic needs update

## System Health Thresholds

| Metric | Warning | Critical |
|---|---|---|
| CPU | > 75% | > 90% |
| Memory | > 75% | > 90% |
| Disk | > 80% | > 90% |
| Trust Stability | > 0.10 weekly delta | > 0.20 weekly delta |
| Calibration | > 0.05 bucket error | > 0.10 bucket error |

## Escalation

1. **Viewer tier** can read all MC data, cannot record outcomes
2. **Operator tier** can record outcomes, run topology queries
3. **Admin tier** required for: bulk import, audit logs, burn-in control, chaos tests

## Chaos Testing

Run monthly to verify resilience:

```bash
# Store resilience
python scripts/hardening/chaos_monkey.py --mode store --duration 60

# Network resilience
python scripts/hardening/chaos_monkey.py --mode network --network-delay 1000

# Memory pressure
python scripts/hardening/chaos_monkey.py --mode memory --duration 60
```

Verify system recovers within 30 seconds after each test.

## Exporting Data

Weekly trust export for stakeholders:

```bash
curl -H "Authorization: Bearer $TOKEN" \
  https://api.uar.local/api/uar/recommendations/trust/export \
  -o "trust-$(date +%Y%m%d).csv"
```

Archive in `data/exports/` with retention policy of 52 weeks.
