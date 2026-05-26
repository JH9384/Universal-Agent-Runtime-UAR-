# UOR Integration Guide

Complete guide for Sigstore signing, Grafana monitoring, and UOR-Foundation integration.

## Quick Start

```bash
# 1. Run integration tests
./scripts/test_integration.sh

# 2. Start monitoring stack
cd deploy && docker-compose -f docker-compose.monitoring.yml up -d

# 3. Verify metrics endpoint
curl http://localhost:8000/metrics | grep uor_alignment

# 4. Push to main to trigger signing
git push origin main
```

## Sigstore Signing (CI/CD)

### Automatic Signing on Push

Every push to `main` triggers automatic signing of UOR artifacts:

```yaml
# .github/workflows/ci.yml
sign-uor-artifacts:
  runs-on: ubuntu-latest
  needs: [python-tests, web-tests]
  if: github.ref == 'refs/heads/main'
  permissions:
    id-token: write  # For Sigstore OIDC
```

### What Gets Signed

- `third_party/uor/*.json` (JSON schemas)
- `third_party/uor/*.ttl` (Turtle ontologies)
- Outputs: `.sig` (signature) + `.cert` (certificate)

### Verifying Signatures Locally

```bash
# Using cosign CLI
cosign verify-blob \
  --bundle third_party/uor/schema.json.sig \
  --certificate third_party/uor/schema.json.cert \
  third_party/uor/schema.json

# Using Python API
from uar.compat.sigstore_signer import verify_artifact
result = verify_artifact(
    "third_party/uor/schema.json",
    "third_party/uor/schema.json.sig"
)
print(f"Valid: {result['valid']}")
```

### GitHub Actions OIDC

Keyless signing uses GitHub Actions OIDC tokens:
- No long-term keys to manage
- Short-lived certificates from Fulcio
- Entries in Rekor transparency log
- Signatures bound to GitHub identity

## Grafana Dashboard

### Dashboard Access

```bash
# Start stack
cd deploy && docker-compose -f docker-compose.monitoring.yml up -d

# Open Grafana
open http://localhost:3000
# Login: admin / admin
```

### Dashboard Panels

1. **UOR Alignment Status** — Drift detection (green=aligned, red=drift)
2. **Artifacts Fresh** — Validation status (green=valid)
3. **Local Version** — Currently pinned UOR version
4. **Upstream Version** — Latest UOR-Foundation release
5. **Alignment Check History** — Time-series of checks
6. **Drift Over Time** — Changes in alignment state

### Metrics Exported

```
# HELP uor_alignment_drift UOR alignment drift detected
# TYPE uor_alignment_drift gauge
uor_alignment_drift 0

# HELP uor_artifacts_fresh Pinned artifacts valid
# TYPE uor_artifacts_fresh gauge
uor_artifacts_fresh 1

# HELP uor_alignment_last_check Last check time
# TYPE uor_alignment_last_check gauge
uor_alignment_last_check 1716662400

# HELP uor_alignment_info UOR alignment version info
# TYPE uor_alignment_info gauge
uor_alignment_info{local="v0.5.2",upstream="v0.5.2"} 1
```

### Webhook Alerts

Configure alerts for drift detection:

```bash
export UOR_WEBHOOK_ENDPOINTS="https://hooks.slack.com/your/webhook"
```

Alerts fire on:
- Alignment drift detected
- Validation failures
- Auto-refresh success/failure

## Provenance CLI

### Verify Run Provenance

```bash
# Verify a specific run
python scripts/uor_provenance.py verify <run_id>

# Export attestation
python scripts/uor_provenance.py export <run_id> --format json
python scripts/uor_provenance.py export <run_id> --format in-toto

# Create attestation bundle
python scripts/uor_provenance.py attest <run_id> --output ./attestation.json
```

### API Endpoint

```bash
# Get provenance data via API
curl -H "Authorization: Bearer $API_KEY" \
  http://localhost:8000/api/provenance/<run_id>
```

Response:
```json
{
  "run_id": "run-abc123",
  "uor_address": "uor-sha256-abc...",
  "uor_witness": "sha256-xyz...",
  "verification": {
    "address_present": true,
    "witness_present": true
  }
}
```

## Upstream Release Watcher

### Check for Updates

```bash
# Single check
python scripts/uor_upstream_watcher.py check

# Check specific tag
python scripts/uor_upstream_watcher.py check --tag v0.5.3
```

### Refresh Pinned Artifacts

```bash
# Manual refresh
python scripts/uor_upstream_watcher.py refresh --tag v0.5.3 --sign --validate

# Auto-refresh mode
python scripts/uor_upstream_watcher.py watch --interval 3600 --auto-refresh
```

### Environment Variables

```bash
UOR_WATCH_INTERVAL=3600      # Polling interval (seconds)
UOR_AUTO_REFRESH=true         # Enable auto-refresh
GITHUB_TOKEN=ghp_xxx          # For private repos
UOR_WEBHOOK_ENDPOINTS=url1,url2  # Alert destinations
```

## Integration Verification

Run full verification:

```bash
# 1. Integration tests
./scripts/test_integration.sh

# 2. API health check
curl http://localhost:8000/api/health

# 3. Metrics endpoint
curl http://localhost:8000/metrics | grep uor_

# 4. Provenance endpoint
curl http://localhost:8000/api/provenance/<run_id>

# 5. Run validation
make validate-uor
```

## Troubleshooting

### Cosign Not Found

```bash
# macOS
brew install sigstore/tap/cosign

# Linux
curl -O -L https://github.com/sigstore/cosign/releases/latest/download/cosign-linux-amd64
chmod +x cosign-linux-amd64
sudo mv cosign-linux-amd64 /usr/local/bin/cosign
```

### Metrics Not Showing

1. Check UAR API is running on port 8000
2. Verify Prometheus config: `deploy/prometheus/prometheus.yml`
3. Check target is up: http://localhost:9090/targets

### Signing Fails in CI

1. Verify `id-token: write` permission in workflow
2. Check workflow runs on `main` branch pushes
3. View Actions logs for specific error

## UOR-Foundation Partnership

See `docs/UOR_FOUNDATION_PARTNERSHIP.md` for:
- Compliance status matrix
- Co-marketing opportunities
- Revenue sharing models
- Success metrics
- Next steps

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                         GitHub Actions                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │ Python Tests │  │  Web Tests   │  │ Sign UOR Artifacts│  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│                          │                                   │
│                          ▼                                   │
│              ┌─────────────────────┐                         │
│              │   cosign sign-blob  │                         │
│              │   (OIDC keyless)    │                         │
│              └─────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                         UAR Runtime                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │   /metrics   │  │ /api/provenance│  │   Run Executor   │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
│         │                │                                   │
│         ▼                ▼                                   │
│  ┌────────────────────────────────────┐                      │
│  │     UOR Alignment Metrics          │                      │
│  │  - Drift detection                 │                      │
│  │  - Version tracking                │                      │
│  │  - Validation status                 │                      │
│  └────────────────────────────────────┘                      │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                      Monitoring Stack                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Prometheus  │  │   Grafana    │  │  Webhook Alerts  │  │
│  │  (scraping)  │  │ (dashboard)  │  │  (notifications) │  │
│  └──────────────┘  └──────────────┘  └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```
