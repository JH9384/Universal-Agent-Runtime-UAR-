from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(slots=True)
class RuntimeHealthStatus:
    runtime_ok: bool = True
    replay_ok: bool = True
    governance_ok: bool = True
    telemetry_ok: bool = True
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "runtime_ok": self.runtime_ok,
            "replay_ok": self.replay_ok,
            "governance_ok": self.governance_ok,
            "telemetry_ok": self.telemetry_ok,
            "metadata": dict(self.metadata),
        }
