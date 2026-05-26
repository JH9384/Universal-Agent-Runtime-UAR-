"""Run certificate primitives for Phase 3A.

A RunCertificate is a portable summary of runtime trust metadata for one run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass(slots=True)
class RunCertificate:
    run_id: str
    goal_id: str
    runtime_mode: str
    runtime_version: str = "unknown"
    event_schema: str = "uar.event.v1"
    replay_fingerprint: str = ""
    replay_status: str = "unknown"
    policy_status: str = "unknown"
    governance_status: str = "unknown"
    artifacts: List[str] = field(default_factory=list)
    lineage: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal_id": self.goal_id,
            "runtime_mode": self.runtime_mode,
            "runtime_version": self.runtime_version,
            "event_schema": self.event_schema,
            "replay_fingerprint": self.replay_fingerprint,
            "replay_status": self.replay_status,
            "policy_status": self.policy_status,
            "governance_status": self.governance_status,
            "artifacts": list(self.artifacts),
            "lineage": dict(self.lineage),
            "metadata": dict(self.metadata),
        }
