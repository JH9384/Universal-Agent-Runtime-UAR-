#!/usr/bin/env bash
# Pre-commit hook: reject f-strings inside logger calls
# Usage: check_no_fstring_logging.sh file1.py file2.py ...

failed=0
for f in "$@"; do
    if grep -n "logger\." "$f" 2>/dev/null | grep -q 'f"'; then
        echo "ERROR: f-string found in logger call in $f"
        grep -n 'logger\.' "$f" | grep 'f"'
        failed=1
    fi
done
exit $failed
