#!/usr/bin/env python3
"""Runtime governance validation.

Produces reviewable governance artifacts for CI.
"""

from __future__ import annotations

import json
from pathlib import Path

from uar.core.registry import registry


ARTIFACT_DIR = Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)

violations = registry.list_contract_violations()

report = {
    "status": "FAILED" if violations else "PASSED",
    "violations": violations,
    "registered_skills": registry.list(),
}

output_path = ARTIFACT_DIR / "runtime_governance_report.json"
output_path.write_text(json.dumps(report, indent=2, sort_keys=True))

print(json.dumps(report, indent=2, sort_keys=True))

if violations:
    raise SystemExit(1)
