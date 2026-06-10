#!/usr/bin/env bash
set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:-local-admin-key}"
RUN_ID="${RUN_ID:-d5h-live}"
REPORT_DIR="${REPORT_DIR:-reports/evidence_pack/live/${RUN_ID}}"

mkdir -p "${REPORT_DIR}"

echo "Capturing live UAR evidence for run: ${RUN_ID}"
echo "API URL: ${API_URL}"
echo "Report dir: ${REPORT_DIR}"

if ! curl -fsS -H "Authorization: Bearer ${API_KEY}" "${API_URL}/api/health" > "${REPORT_DIR}/health.json"; then
  echo "D5H live evidence pack capture: FAIL"
  echo "UAR API is not reachable at ${API_URL}."
  echo "Start it with:"
  echo "  export API_KEYS=\"local-admin-key:admin:local-d5h\""
  echo "  export UAR_AUTH_MODE=\"api_key\""
  echo "  python -m uar.boot --services api"
  exit 1
fi

python -m json.tool "${REPORT_DIR}/health.json" >/dev/null

if ! curl -fsS -H "Authorization: Bearer ${API_KEY}" "${API_URL}/api/health" > "${REPORT_DIR}/health.json"; then
  echo "D5H live evidence pack capture: FAIL"
  echo "UAR API is not reachable at ${API_URL}."
  echo "Start it with:"
  echo "  export API_KEYS=\"local-admin-key:admin:local-d5h\""
  echo "  export UAR_AUTH_MODE=\"api_key\""
  echo "  python -m uar.boot --services api"
  exit 1
fi

python -m json.tool "${REPORT_DIR}/health.json" >/dev/null

curl -sS -H "Authorization: Bearer ${API_KEY}" \
  "${API_URL}/api/uar/mission-control" \
  | python -m json.tool > "${REPORT_DIR}/mission_control.json"

curl -sS -H "Authorization: Bearer ${API_KEY}" \
  "${API_URL}/api/uar/certification" \
  | python -m json.tool > "${REPORT_DIR}/certification.json"

curl -sS -H "Authorization: Bearer ${API_KEY}" \
  "${API_URL}/api/uar/burnin/latest" \
  | python -m json.tool > "${REPORT_DIR}/burnin.json"

python scripts/evidence_pack/build_evidence_pack.py \
  --run-id "${RUN_ID}" \
  --output-dir "${REPORT_DIR}" \
  --authority-tag "v1.2.21-d5g-evidence-pack-cli" \
  --mission-control-json "${REPORT_DIR}/mission_control.json" \
  --certification-json "${REPORT_DIR}/certification.json" \
  --burnin-json "${REPORT_DIR}/burnin.json"

python -m json.tool "${REPORT_DIR}/${RUN_ID}_evidence_pack.json" >/dev/null
test -s "${REPORT_DIR}/${RUN_ID}_evidence_pack.md"

echo "D5H live evidence pack capture: PASS"
echo "${REPORT_DIR}/${RUN_ID}_evidence_pack.json"
echo "${REPORT_DIR}/${RUN_ID}_evidence_pack.md"
