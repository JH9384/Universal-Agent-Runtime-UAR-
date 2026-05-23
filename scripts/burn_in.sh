#!/usr/bin/env bash
set -euo pipefail

printf '\n== UAR Burn-In: deterministic runtime substrate ==\n\n'

printf '== Version check ==\n'
make version
make sync-version

printf '\n== Targeted planner/config/event tests ==\n'
pytest tests/test_planner_router.py -q
pytest tests/test_runtime_config.py -q
pytest tests/test_runtime_events.py -q

printf '\n== Targeted replay/timeline/certification tests ==\n'
pytest tests/test_replay_integrity.py -q
pytest tests/test_timeline.py -q
pytest tests/test_runtime_trace_fixtures.py -q
pytest tests/test_replay_certification.py -q

printf '\n== Full gate ==\n'
make gate

printf '\n== Burn-In Complete ==\n'
printf 'Runtime substrate checks passed. No feature expansion performed.\n'
