from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RuntimeReleaseBundle:
    version: str
    manifests: List[str] = field(default_factory=list)
    artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "manifests": list(self.manifests),
            "artifacts": list(self.artifacts),
            "metadata": dict(self.metadata),
        }
