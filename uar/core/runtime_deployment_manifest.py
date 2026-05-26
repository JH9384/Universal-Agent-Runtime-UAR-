from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RuntimeDeploymentManifest:
    environment: str
    runtime_version: str
    startup_commands: List[str] = field(default_factory=list)
    services: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "environment": self.environment,
            "runtime_version": self.runtime_version,
            "startup_commands": list(self.startup_commands),
            "services": list(self.services),
            "metadata": dict(self.metadata),
        }
