from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RuntimeCapability:
    name: str
    version: str
    enabled: bool = True

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "enabled": self.enabled,
        }


@dataclass(slots=True)
class RuntimeCapabilityManifest:
    runtime_version: str
    capabilities: List[RuntimeCapability] = field(default_factory=list)

    def add(self, capability: RuntimeCapability) -> None:
        self.capabilities.append(capability)

    def to_dict(self) -> Dict[str, object]:
        return {
            "runtime_version": self.runtime_version,
            "capabilities": [capability.to_dict() for capability in self.capabilities],
        }
