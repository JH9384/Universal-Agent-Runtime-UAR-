#!/usr/bin/env bash
# Pre-commit hook: catch recurring bug patterns found in bug-bounty
# sessions.  Checks:
#   1. f-strings inside logger calls
#   2. bare ``except Exception:`` without a logging call in the block
#   3. ``time.time()`` used for timeout / deadline calculations
#   4. ``getattr(..., "id", ...)`` — frequent silent-data-corruption source
# Usage: check_bug_patterns.sh file1.py file2.py ...

failed=0
for f in "$@"; do
    python3 -c "
import re, sys

def fail(msg):
    print(f'ERROR in {fname}: {msg}')
    sys.exit(1)

fname = '$f'
try:
    content = open(fname, encoding='utf-8', errors='ignore').read()
except Exception:
    sys.exit(0)

# 1. f-string in logger call
if re.search(
    r'(logger|logging)\.(debug|info|warning|error|critical)\s*\([^)]*f\"',
    content,
    re.DOTALL,
):
    fail('f-string found in logger call')

# 2. bare except Exception with no logging / raise inside the block
# Heuristic: find 'except Exception:' blocks that lack logger/logging
# and do NOT re-raise the exception.
for block in re.finditer(
    r'except\s+Exception\s*:\s*\n((?:\s+.*\n)*)',
    content,
):
    body = block.group(1)
    if 'raise' in body:
        continue
    if 'logger' not in body and 'logging' not in body:
        fail('bare except Exception without logging')

# 3. time.time() used for timeout (not simple elapsed measurement)
# Flag only when combined with +, comparison operators, deadline, timeout.
# NOTE: ``time.time() - t0`` (elapsed measurement) is NOT flagged.
if re.search(
    r'time\.time\(\)\s*\+|'
    r'time\.time\(\)\s*[<>=]=?\s*\d+|'
    r'time\.time\(\).*(?:timeout|deadline)|'
    r'(?:timeout|deadline).*time\.time\(\)',
    content,
):
    fail('time.time() used for timeout/deadline (use time.monotonic())')

# 4. getattr(..., 'id', ...) — historically causes silent corruption
if re.search(r'getattr\([^,]*,\s*["\x27]id["\x27]', content):
    fail('getattr(..., \"id\", ...) — verify field name matches object schema')

" 2>/dev/null || failed=1
done
exit $failed
