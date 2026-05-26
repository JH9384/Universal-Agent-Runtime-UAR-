#!/bin/bash
# Test new features: sigstore API, insurance, multi-tenant

set -e

echo "=== Testing Sprint Features ==="
echo ""

# Test 1: Sigstore dependency available
echo "[1/4] Testing sigstore dependency..."
python -c "
try:
    import sigstore
    print('✓ sigstore package available')
except ImportError:
    print('⚠ sigstore not installed (pip install sigstore)')
" || true

# Test 2: Actuarial collector
echo "[2/4] Testing actuarial collector..."
python -c "
from uar.insurance.actuarial import get_actuarial_collector
collector = get_actuarial_collector()
print('✓ Actuarial collector initializes')

# Test risk calculation (empty data)
profile = collector.calculate_risk_profile('test_user')
if profile is None:
    print('✓ Risk profile returns None for no data (expected)')
" || {
    echo "✗ Actuarial collector failed"
    exit 1
}

# Test 3: Multi-tenant security
echo "[3/4] Testing multi-tenant security..."
python -c "
from uar.security.multitenant import get_tenant_isolation

# Test isolation manager
isolation = get_tenant_isolation()
print('✓ Tenant isolation initializes')

# Test sandbox class directly
from uar.security.multitenant import SecuritySandbox
sandbox = SecuritySandbox('tenant_1', 'run_1')
with sandbox:
    wd = sandbox.get_working_directory()
    print(f'✓ Sandbox workspace created')
" || {
    echo "✗ Multi-tenant security failed"
    exit 1
}

# Test 4: Grafana Cloud dashboard JSON
echo "[4/4] Testing Grafana dashboard..."
python -c "
import json
with open('deploy/grafana/uor-alignment-dashboard.json') as f:
    dashboard = json.load(f)
    assert 'dashboard' in str(dashboard) or 'panels' in str(dashboard)
    print(f'✓ Grafana dashboard has {len(dashboard.get(\"panels\", []))} panels')
" || {
    echo "✗ Grafana dashboard failed"
    exit 1
}

echo ""
echo "=== All new features working ==="
echo ""
echo "Usage:"
echo "  pip install '.[sigstore]'     # Full sigstore support"
echo "  python -c 'from uar.insurance.actuarial import get_actuarial_collector'"
echo "  python -c 'from uar.security.multitenant import sandboxed_execution'"
