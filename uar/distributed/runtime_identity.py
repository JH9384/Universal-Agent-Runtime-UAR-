from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class RuntimeIdentity:
    identity_id: str
    roles: List[str] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, object]:
        return {
            "identity_id": self.identity_id,
            "roles": list(self.roles),
            "metadata": dict(self.metadata),
        }
