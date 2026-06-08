#!/usr/bin/env bash
set -euo pipefail

API_URL="${UAR_SMOKE_API_URL:-http://127.0.0.1:${UAR_API_PORT:-8000}}"
MAX_ATTEMPTS="${UAR_SMOKE_ATTEMPTS:-30}"
SLEEP_SECONDS="${UAR_SMOKE_SLEEP:-2}"

printf '== UAR Docker smoke ==\n'
printf 'API URL: %s\n' "$API_URL"

health_ok=0
for attempt in $(seq 1 "$MAX_ATTEMPTS"); do
  if curl -fsS "$API_URL/api/health" >/tmp/uar-health.json 2>/dev/null; then
    health_ok=1
    break
  fi
  if curl -fsS "$API_URL/health" >/tmp/uar-health.json 2>/dev/null; then
    health_ok=1
    break
  fi
  printf 'waiting for API health (%s/%s)\n' "$attempt" "$MAX_ATTEMPTS"
  sleep "$SLEEP_SECONDS"
done

if [[ "$health_ok" != "1" ]]; then
  printf 'ERROR: API health check failed after %s attempts\n' "$MAX_ATTEMPTS" >&2
  exit 1
fi

printf 'Health: PASS\n'
cat /tmp/uar-health.json
printf '\n'

# Mission Control may require auth in hardened configurations; treat 401/403 as
# proof that the route is alive and guarded, not as a Docker smoke failure.
mission_status="$({ curl -sS -o /tmp/uar-mission.json -w '%{http_code}' "$API_URL/api/uar/mission-control" || true; })"
case "$mission_status" in
  200)
    printf 'Mission Control: PASS\n'
    cat /tmp/uar-mission.json
    printf '\n'
    ;;
  401|403)
    printf 'Mission Control: guarded (%s)\n' "$mission_status"
    ;;
  *)
    printf 'ERROR: Mission Control unexpected HTTP %s\n' "$mission_status" >&2
    cat /tmp/uar-mission.json >&2 || true
    exit 1
    ;;
esac

printf 'Docker smoke: PASS\n'
