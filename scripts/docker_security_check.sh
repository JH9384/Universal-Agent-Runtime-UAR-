#!/usr/bin/env bash
set -euo pipefail

SERVICE="${1:-uar-api}"

uid="$(docker compose run --rm --entrypoint id "$SERVICE" -u)"
gid="$(docker compose run --rm --entrypoint id "$SERVICE" -g)"

echo "Docker runtime UID: $uid"
echo "Docker runtime GID: $gid"

if [ "$uid" = "0" ]; then
  echo "ERROR: Docker service is running as root"
  exit 1
fi

if [ "$uid" != "10001" ]; then
  echo "ERROR: Expected UID 10001, got $uid"
  exit 1
fi

echo "Docker non-root check: PASS"
