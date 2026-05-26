from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class SyncGovernance:
    governance_id: str
    rules: List[str] = field(default_factory=list)
    escalation_paths: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "governance_id": self.governance_id,
            "rules": list(self.rules),
            "escalation_paths": list(self.escalation_paths),
        }
