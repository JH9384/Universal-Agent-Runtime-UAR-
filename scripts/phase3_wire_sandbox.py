#!/usr/bin/env python3
"""Safely wire apps/api-python/main.py to the extracted sandbox module.

This script intentionally performs a tiny, auditable patch instead of replacing
main.py wholesale. It refuses to proceed unless the expected source patterns are
present and the final change is limited to the sandbox import plus one call-site
replacement.
"""

from __future__ import annotations

from pathlib import Path
import difflib
import sys

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "apps" / "api-python" / "main.py"

IMPORT_ANCHOR = "import uuid\n"
IMPORT_LINE = "from sandbox import run_code as sandbox_run_code\n"
OLD_CALL = "    result = run_code(code, input_objects, parameters)\n"
NEW_CALL = "    result = sandbox_run_code(code, input_objects, parameters)\n"


def main() -> int:
    original = MAIN.read_text()
    updated = original

    if IMPORT_LINE not in updated:
        if IMPORT_ANCHOR not in updated:
            print("ERROR: import anchor not found", file=sys.stderr)
            return 1
        updated = updated.replace(IMPORT_ANCHOR, IMPORT_ANCHOR + IMPORT_LINE, 1)

    if OLD_CALL not in updated:
        print("ERROR: expected run_code call site not found", file=sys.stderr)
        return 1
    updated = updated.replace(OLD_CALL, NEW_CALL, 1)

    diff = list(difflib.unified_diff(
        original.splitlines(),
        updated.splitlines(),
        fromfile="main.py.before",
        tofile="main.py.after",
        lineterm="",
    ))

    changed_lines = [line for line in diff if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]
    if len(changed_lines) > 4:
        print("ERROR: patch changed more lines than expected", file=sys.stderr)
        print("\n".join(diff), file=sys.stderr)
        return 1

    MAIN.write_text(updated)
    print("Sandbox wiring patch applied safely.")
    print("\n".join(diff))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
