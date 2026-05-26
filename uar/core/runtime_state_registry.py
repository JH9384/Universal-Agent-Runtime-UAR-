from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict


@dataclass(slots=True)
class RuntimeStateSnapshot:
    category: str
    state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "state": dict(self.state),
        }


class RuntimeStateRegistry:
    def __init__(self) -> None:
        self.snapshots: Dict[str, RuntimeStateSnapshot] = {}

    def put(self, snapshot: RuntimeStateSnapshot) -> None:
        self.snapshots[snapshot.category] = snapshot

    def get(self, category: str) -> RuntimeStateSnapshot | None:
        return self.snapshots.get(category)

    def to_dict(self) -> Dict[str, object]:
        return {
            key: snapshot.to_dict()
            for key, snapshot in self.snapshots.items()
        }
