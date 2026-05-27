from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RuntimePackageManifest:
    name: str
    version: str
    runtime_modes: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "version": self.version,
            "runtime_modes": list(self.runtime_modes),
            "dependencies": list(self.dependencies),
            "metadata": dict(self.metadata),
        }
