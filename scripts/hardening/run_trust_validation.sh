#!/usr/bin/env bash
# Ω-7B.1 Trust Validation — Weekly operational validation runner.
#
# Usage:
#   ./scripts/hardening/run_trust_validation.sh [--api-url URL] [--api-key KEY]
#
# Archives timestamped JSON reports to:
#   reports/trust_validation/

set -euo pipefail

API_URL="${API_URL:-http://127.0.0.1:8000}"
API_KEY="${API_KEY:-dev-key-12345}"

# Parse arguments
while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-url) API_URL="$2"; shift 2 ;;
    --api-key) API_KEY="$2"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

REPORT_DIR="reports/trust_validation"
mkdir -p "$REPORT_DIR"

TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTFILE="$REPORT_DIR/trust_validation_${TIMESTAMP}.json"

echo "Ω-7B.1 Trust Validation — $TIMESTAMP"
echo "API: $API_URL"
echo "Output: $OUTFILE"

python scripts/hardening/trust_validation.py \
  --api-url "$API_URL" \
  --api-key "$API_KEY" \
  --output "$OUTFILE"

echo "Report archived: $OUTFILE"

# Optional: keep only last 52 reports (one year weekly)
ls -1t "$REPORT_DIR"/trust_validation_*.json 2>/dev/null | \
  tail -n +53 | \
  xargs -r rm -f

echo "Done."
