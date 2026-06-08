#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTEST_BIN="${PYTEST_BIN:-.venv/bin/python -m pytest}"
OUT_DIR="${D4D_BACKEND_SLICE_DIR:-artifacts/d4d/backend-slices}"
mkdir -p "$OUT_DIR"

if command -v ulimit >/dev/null 2>&1; then
  ulimit -n "${D4D_ULIMIT_NOFILE:-4096}" 2>/dev/null || true
fi

SLICES=(
  "tests/core"
  "tests/api"
  "tests/runtime"
  "tests/store"
  "tests/skills"
  "tests/unit"
  "tests/integration"
  "tests/uor"
  "tests/docs"
  "tests/security"
  "tests/performance"
  "tests/regression"
  "tests/objects"
  "tests/conformance"
  "tests/bug_patterns"
)

FAILURES=()
PASSED=()
SKIPPED=()

echo "== D4D backend sliced validation =="
echo "Output directory: $OUT_DIR"
echo "Pytest: $PYTEST_BIN"
echo "Open-file soft limit: $(ulimit -n 2>/dev/null || echo unknown)"
echo

for slice in "${SLICES[@]}"; do
  if [[ ! -d "$slice" ]]; then
    SKIPPED+=("$slice")
    continue
  fi

  safe_name="${slice//\//_}"
  log_path="$OUT_DIR/${safe_name}.log"
  echo "== Running $slice =="
  if $PYTEST_BIN "$slice" -q --tb=short 2>&1 | tee "$log_path"; then
    PASSED+=("$slice")
    echo "PASS $slice"
  else
    FAILURES+=("$slice")
    echo "FAIL $slice — see $log_path"
  fi
  echo

done

summary_path="$OUT_DIR/summary.md"
{
  echo "# D4D Backend Sliced Validation Summary"
  echo
  echo "Generated: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo
  echo "Open-file soft limit: $(ulimit -n 2>/dev/null || echo unknown)"
  echo
  echo "## Passed"
  if [[ ${#PASSED[@]} -eq 0 ]]; then
    echo
    echo "- none"
  else
    printf -- '- %s\n' "${PASSED[@]}"
  fi
  echo
  echo "## Failed"
  if [[ ${#FAILURES[@]} -eq 0 ]]; then
    echo
    echo "- none"
  else
    printf -- '- %s\n' "${FAILURES[@]}"
  fi
  echo
  echo "## Skipped"
  if [[ ${#SKIPPED[@]} -eq 0 ]]; then
    echo
    echo "- none"
  else
    printf -- '- %s\n' "${SKIPPED[@]}"
  fi
} > "$summary_path"

echo "== Summary =="
cat "$summary_path"

if [[ ${#FAILURES[@]} -gt 0 ]]; then
  exit 1
fi
