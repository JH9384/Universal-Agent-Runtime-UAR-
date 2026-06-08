#!/usr/bin/env bash
# Validate D4C reuse-first fleet + operator daily loop.
#
# This script intentionally runs the focused D4C regression slice before the
# broader frontend build/test checks. It creates no artifacts and does not
# require a running UAR server.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "== D4C backend regression slice =="
pytest \
  tests/core/test_fleet_signals.py \
  tests/core/test_fleet_alerts.py \
  tests/core/test_fleet_linkage.py \
  tests/core/test_fleet_outcome_trust_movement.py \
  tests/core/test_fleet_evidence_section.py \
  tests/core/test_incident_evidence_section.py \
  tests/core/test_evidence_pack_v2.py \
  tests/core/test_operator_daily_briefing.py \
  tests/core/test_incident_intelligence.py \
  tests/api/test_mission_control.py

echo "== D4C frontend operator loop tests =="
cd "$ROOT_DIR/apps/web"
npm run test:run -- \
  src/components/AlertBanner.test.tsx \
  src/components/mission-control/OperatorBriefingPanel.test.tsx \
  src/components/mission-control/FocusModePanel.test.tsx \
  src/components/mission-control/IncidentRecurrenceSummary.test.tsx \
  src/components/mission-control/RecommendationOutcomeCapture.test.tsx \
  src/components/mission-control/ArtifactBrowser.test.tsx \
  src/components/Dashboard.test.tsx \
  src/utils/downloadMarkdown.test.ts \
  src/utils/evidencePackPreview.test.ts \
  src/utils/recurrenceNotes.test.ts

echo "== Frontend production build =="
npm run build

echo "D4C operator loop validation complete."
