#!/usr/bin/env python3
import json
import os
from pathlib import Path

report_dir = Path(os.environ.get("REPORT_DIR", "reports/d4e"))

burnin_run = json.loads((report_dir / "burnin_run.json").read_text())
mission_control = json.loads((report_dir / "mission_control.json").read_text())
certification = json.loads((report_dir / "certification.json").read_text())

summary = {
    "status": "PASS",
    "artifact_dir": str(report_dir),
    "mission_control_keys": sorted(mission_control.keys())[:20],
    "certification_keys": sorted(certification.keys())[:20],
    "burnin_passed": burnin_run.get("passed"),
    "burnin_score": burnin_run.get("score"),
}

(report_dir / "runtime_smoke_summary.json").write_text(
    json.dumps(summary, indent=2, sort_keys=True) + "\n"
)

print(json.dumps(summary, indent=2, sort_keys=True))
