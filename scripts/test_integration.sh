#!/bin/bash
# Integration test for Sigstore signing and UOR monitoring

set -e

echo "=== UOR Integration Test ==="
echo ""

# Test 1: Verify sigstore signer module loads
echo "[1/5] Testing Sigstore signer module..."
python -c "from uar.compat.sigstore_signer import sign_artifact, verify_artifact; print('✓ Sigstore module loads')" || {
    echo "✗ Sigstore module failed to load"
    exit 1
}

# Test 2: Verify UOR alignment metrics
echo "[2/5] Testing UOR alignment metrics..."
python -c "
from uar.api.uor_alignment_metrics import get_uor_alignment_metrics
metrics = get_uor_alignment_metrics()
metrics.record_alignment_check('v0.5.2', 'v0.5.2', True)
output = metrics.get_prometheus_metrics()
assert 'uor_alignment_drift' in output
assert 'uor_artifacts_fresh' in output
print('✓ UOR alignment metrics working')
" || {
    echo "✗ UOR alignment metrics failed"
    exit 1
}

# Test 3: Verify webhook alerter
echo "[3/5] Testing webhook alerter..."
python -c "
from uar.api.webhook_alerts import get_webhook_alerter
alerter = get_webhook_alerter()
# Test without actual endpoints (just loads)
print('✓ Webhook alerter loads')
" || {
    echo "✗ Webhook alerter failed"
    exit 1
}

# Test 4: Check cosign availability (optional)
echo "[4/5] Checking cosign CLI..."
if command -v cosign &> /dev/null; then
    cosign version | head -1
    echo "✓ cosign CLI available"
else
    echo "⚠ cosign CLI not found (install: brew install sigstore/tap/cosign)"
fi

# Test 5: Verify dashboard JSON is valid
echo "[5/5] Validating Grafana dashboard..."
python -c "
import json
with open('deploy/grafana/dashboards/dashboard-uor-alignment.json') as f:
    dashboard = json.load(f)
    assert 'dashboard' in dashboard
    assert 'title' in dashboard['dashboard']
    print('✓ Grafana dashboard JSON valid')
" || {
    echo "✗ Dashboard JSON invalid"
    exit 1
}

echo ""
echo "=== All integration tests passed ==="
echo ""
echo "Next steps:"
echo "  1. Start monitoring: cd deploy && docker-compose -f docker-compose.monitoring.yml up -d"
echo "  2. Run UAR API with metrics enabled"
echo "  3. Push to main branch to trigger signing workflow"
echo "  4. View dashboard at http://localhost:3000 (admin/admin)"
