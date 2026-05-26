from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class RuntimeIngressRecord:
    ingress_id: str
    runtime_mode: str
    replay_safe: bool
    authority_validated: bool
    lineage_continuity: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "ingress_id": self.ingress_id,
            "runtime_mode": self.runtime_mode,
            "replay_safe": self.replay_safe,
            "authority_validated": self.authority_validated,
            "lineage_continuity": self.lineage_continuity,
        }
