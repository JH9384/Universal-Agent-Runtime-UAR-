#!/usr/bin/env bash
set -euo pipefail

printf '\n== UAR Burn-In ==\n\n'

printf '== Version sync ==\n'
make version
make sync-version

printf '\n== Runtime substrate tests ==\n'
pytest tests/test_planner_router.py -q
pytest tests/test_runtime_config.py -q
pytest tests/test_runtime_events.py -q
pytest tests/test_replay_integrity.py -q
pytest tests/test_timeline.py -q
pytest tests/test_runtime_trace_fixtures.py -q
pytest tests/test_replay_certification.py -q

printf '\n== Expanded baseline tests ==\n'
pytest tests/test_math_plot.py -q

printf '\n== Full gate ==\n'
make gate

printf '\n== Burn-In Complete ==\n'
printf 'Baseline stabilized with no unreviewed semantic drift.\n'
