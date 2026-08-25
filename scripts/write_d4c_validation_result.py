#!/usr/bin/env python3
"""Write a D4C validation result stub.

This helper records environment metadata and leaves result fields editable.
It does not run validation; run `make d4c-release-gate` to execute the
focused gate and write the result stub together.
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
    operator = (
        os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    )
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"d4c-validation-{now}.md"
    out_path.write_text(
        f"""# D4C Validation Result

> Generated: {now}

---

## Command

```bash
make d4c-release-gate
```

---

## Environment

- Date: {now}
- Operator: {operator}
- Branch: {branch}
- Commit: {commit}
- Python version: {python_version}
- Node version: {node_version}
- OS: {platform.platform()}

---

## Result

- Overall result: PASS / FAIL
- Backend D4C regression slice: PASS / FAIL
- Frontend D4C tests: PASS / FAIL
- Frontend production build: PASS / FAIL

---

## Failures

| Area | Test/Step | Failure summary | Action |
|------|-----------|-----------------|--------|
|      |           |                 |        |

---

## Anti-Sprawl Check

- [ ] no incident console
- [ ] no incident store
- [ ] no duplicate endpoint
- [ ] no new dashboard
- [ ] no parallel workflow
- [ ] no second trust score
- [ ] no parallel evidence pipeline

---

## Decision

- [ ] Ready to continue to export/runbook polish
- [ ] Not ready; fix validation failures first
""",
        encoding="utf-8",
    )
    print(out_path.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
