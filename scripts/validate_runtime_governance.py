#!/usr/bin/env python3
"""Runtime governance validation.

Produces reviewable governance artifacts for CI and Phase 1/2 closure review.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

from uar.core.registry import registry


ARTIFACT_DIR = Path("artifacts")
ARTIFACT_DIR.mkdir(exist_ok=True)

violations = registry.list_contract_violations()

phase_closure: Dict[str, Any] = {
    "phase_1_runtime_stabilization": {
        "status": "CLOSED_FOR_GOVERNANCE",
        "runtime_truth": "RuntimeEvent + RunRecord",
        "required_follow_on_validation": [
            "golden replay fixture expansion",
            "repeated burn-in execution",
            "long-run replay drift testing",
        ],
    },
    "phase_2_runtime_governance": {
        "status": "IMPLEMENTATION_HARDENING_ACTIVE",
        "runtime_governance_surfaces": [
            "SkillContract",
            "GovernanceDecision",
            "ReplayCertificationReport",
            "RuntimeEvent compatibility matrix",
            "canonical replay fingerprinting",
        ],
    },
}

report = {
    "status": "FAILED" if violations else "PASSED",
    "violations": violations,
    "registered_skills": registry.list(),
    "phase_closure": phase_closure,
}

output_path = ARTIFACT_DIR / "runtime_governance_report.json"
output_path.write_text(json.dumps(report, indent=2, sort_keys=True))

phase_output_path = ARTIFACT_DIR / "phase_1_2_closure_report.json"
phase_output_path.write_text(json.dumps(phase_closure, indent=2, sort_keys=True))

print(json.dumps(report, indent=2, sort_keys=True))

if violations:
    raise SystemExit(1)
