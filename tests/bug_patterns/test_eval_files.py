"""Eval-file test runner for UAR bug-pattern detection.

Pattern borrowed from PyCQA/flake8-bugbear's test_bugbear.py.
Each eval file contains Python code with inline annotations::

    # UAR001: <col>

indicating an expected violation at that line and column.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

EVAL_DIR = Path(__file__).parent / "eval_files"

ERROR_CODES = {
    "UAR001": "f-string in logger call",
    "UAR002": "bare except Exception without logging",
    "UAR003": "time.time() used for timeout/deadline",
}


def _parse_eval_file(path: Path) -> list[tuple[int, int, str]]:
    """Extract expected (lineno, col, code) tuples from eval file comments."""
    expected: list[tuple[int, int, str]] = []
    for lineno, line in enumerate(path.read_text().split("\n"), start=1):
        # Match ``# UAR001: 0`` or ``# UAR002: 4`` etc.
        for match in re.finditer(r"#\s*(UAR\d\d\d):\s*(\d+)", line):
            code = match.group(1)
            col = int(match.group(2))
            expected.append((lineno, col, code))
    return expected


def _run_hook(path: Path) -> list[tuple[int, int, str]]:
    """Run the pre-commit hook against a single file and parse its output."""
    hook = (
        Path(__file__).parents[2] / "scripts" / "check_no_fstring_logging.sh"
    )
    proc = subprocess.run(
        ["bash", str(hook), str(path)],
        capture_output=True,
        text=True,
    )
    # Hook exits 1 when violations are found, 0 when clean
    errors: list[tuple[int, int, str]] = []
    if proc.returncode == 0:
        return errors
    for line in proc.stderr.splitlines() + proc.stdout.splitlines():
        # Parse ``ERROR in file.py: <message>``
        if not line.startswith("ERROR"):
            continue
        msg = line.split(":", 2)[-1].strip().lower()
        if "f-string" in msg:
            errors.append((0, 0, "UAR001"))
        elif "bare except" in msg:
            errors.append((0, 0, "UAR002"))
        elif "time.time()" in msg:
            errors.append((0, 0, "UAR003"))
    return errors


# Collect all eval files and build parametrized test matrix
eval_files = sorted(EVAL_DIR.glob("*.py"))


@pytest.mark.parametrize(
    "eval_path", eval_files, ids=[f.name for f in eval_files]
)
def test_eval_file(eval_path: Path) -> None:
    expected = _parse_eval_file(eval_path)
    actual = _run_hook(eval_path)

    # For the shell hook we can only check counts per rule, not line/col
    expected_counts: dict[str, int] = {}
    actual_counts: dict[str, int] = {}
    for _, _, code in expected:
        expected_counts[code] = expected_counts.get(code, 0) + 1
    for _, _, code in actual:
        actual_counts[code] = actual_counts.get(code, 0) + 1

    assert actual_counts == expected_counts, (
        f"Mismatch for {eval_path.name}\n"
        f"Expected: {expected_counts}\n"
        f"Actual:   {actual_counts}"
    )
