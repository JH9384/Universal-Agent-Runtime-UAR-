#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:-local-admin-key}"
RUN_ID="${RUN_ID:-d5w-api-smoke}"
REPORT_DIR="${REPORT_DIR:-reports/d5w}"

mkdir -p "${REPORT_DIR}"

echo "D5W Evidence Pack API smoke"
echo "API URL: ${API_URL}"
echo "Run ID: ${RUN_ID}"
echo "Report dir: ${REPORT_DIR}"

if ! curl -fsS -H "Authorization: Bearer ${API_KEY}" "${API_URL}/api/health" > "${REPORT_DIR}/health.json"; then
  echo "D5W evidence pack API smoke: FAIL"
  echo "UAR API is not reachable at ${API_URL}."
  echo "Start it with:"
  echo "  export API_KEYS=\"local-admin-key:admin:local-d5w\""
  echo "  export UAR_AUTH_MODE=\"api_key\""
  echo "  python -m uar.boot --services api"
  exit 1
fi

python -m json.tool "${REPORT_DIR}/health.json" >/dev/null

curl -fsS \
  -H "Authorization: Bearer ${API_KEY}" \
  "${API_URL}/api/uar/evidence-pack/${RUN_ID}" \
  | python -m json.tool > "${REPORT_DIR}/evidence_pack_basic.json"

curl -fsS \
  -H "Authorization: Bearer ${API_KEY}" \
  "${API_URL}/api/uar/evidence-pack/${RUN_ID}?include_markdown=true" \
  | python -m json.tool > "${REPORT_DIR}/evidence_pack_markdown.json"

curl -sS \
  "${API_URL}/api/uar/evidence-pack/${RUN_ID}" \
  | python -m json.tool > "${REPORT_DIR}/evidence_pack_unauth.json" || true

python - <<'PY'
import json
import os
from pathlib import Path

report_dir = Path(os.environ.get("REPORT_DIR", "reports/d5w"))
run_id = os.environ.get("RUN_ID", "d5w-api-smoke")

basic = json.loads((report_dir / "evidence_pack_basic.json").read_text())
markdown = json.loads((report_dir / "evidence_pack_markdown.json").read_text())
unauth = json.loads((report_dir / "evidence_pack_unauth.json").read_text())

assert basic["status"] == "ok"
assert basic["run_id"] == run_id
assert basic["markdown"] is None
assert basic["evidence_pack"]["evidence_pack_id"] == f"evidence-pack:{run_id}"

assert isinstance(markdown["markdown"], str)
assert "Evidence Pack v2" in markdown["markdown"]
assert run_id in markdown["markdown"]

assert unauth["detail"]["error"] == "unauthorized"
assert unauth["detail"]["message"] == "Authentication required"

summary = {
    "status": "PASS",
    "run_id": run_id,
    "basic": str(report_dir / "evidence_pack_basic.json"),
    "markdown": str(report_dir / "evidence_pack_markdown.json"),
    "unauth": str(report_dir / "evidence_pack_unauth.json"),
}
(report_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
print(json.dumps(summary, indent=2, sort_keys=True))
PY

echo "D5W evidence pack API smoke: PASS"
