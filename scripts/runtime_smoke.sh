#!/usr/bin/env bash
set -euo pipefail

export PYTHONPATH="${PYTHONPATH:-.}"

python - <<'PY'
from uar.core.runtime_health import RuntimeHealthStatus
from uar.core.runtime_transport import RuntimeTransportBuffer

health = RuntimeHealthStatus()
transport = RuntimeTransportBuffer()
transport.send(topic='runtime.smoke', payload={'ok': True})

print('runtime_ok=', health.runtime_ok)
print('transport_events=', len(transport.flush()))
PY
