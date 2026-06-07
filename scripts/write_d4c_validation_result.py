#!/usr/bin/env python3
"""Write a D4C validation result stub.

This helper records environment metadata and leaves result fields editable.
It does not run validation; run `make validate-d4c` first.
"""

from __future__ import annotations

import datetime as _dt
import os
import platform
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "operations" / "validation-results"


def _cmd(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, cwd=ROOT, text=True).strip()
    except Exception:
        return "unknown"


def main() -> int:
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    commit = _cmd(["git", "rev-parse", "HEAD"])
    branch = _cmd(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    python_version = platform.python_version()
    node_version = _cmd(["node", "--version"])
    operator = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"d4c-validation-{now}.md"
    out_path.write_text(
        f"""# D4C Validation Result\n\n"
        f"> Generated: {now}\n\n"
        f"---\n\n"
        f"## Command\n\n"
        f"```bash\nmake validate-d4c\n```\n\n"
        f"---\n\n"
        f"## Environment\n\n"
        f"- Date: {now}\n"
        f"- Operator: {operator}\n"
        f"- Branch: {branch}\n"
        f"- Commit: {commit}\n"
        f"- Python version: {python_version}\n"
        f"- Node version: {node_version}\n"
        f"- OS: {platform.platform()}\n\n"
        f"---\n\n"
        f"## Result\n\n"
        f"- Overall result: PASS / FAIL\n"
        f"- Backend D4C regression slice: PASS / FAIL\n"
        f"- Frontend D4C tests: PASS / FAIL\n"
        f"- Frontend production build: PASS / FAIL\n\n"
        f"---\n\n"
        f"## Failures\n\n"
        f"| Area | Test/Step | Failure summary | Action |\n"
        f"|------|-----------|-----------------|--------|\n"
        f"|      |           |                 |        |\n\n"
        f"---\n\n"
        f"## Anti-Sprawl Check\n\n"
        f"- [ ] no incident console\n"
        f"- [ ] no incident store\n"
        f"- [ ] no duplicate endpoint\n"
        f"- [ ] no new dashboard\n"
        f"- [ ] no parallel workflow\n"
        f"- [ ] no second trust score\n"
        f"- [ ] no parallel evidence pipeline\n\n"
        f"---\n\n"
        f"## Decision\n\n"
        f"- [ ] Ready to continue to export/runbook polish\n"
        f"- [ ] Not ready; fix validation failures first\n"
        f""",
        encoding="utf-8",
    )
    print(out_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
