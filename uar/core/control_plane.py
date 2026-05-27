from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(slots=True)
class ControlPlanePanel:
    name: str
    status: str
    payload: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "payload": dict(self.payload),
        }


class RuntimeControlPlane:
    def __init__(self) -> None:
        self.panels: List[ControlPlanePanel] = []

    def add_panel(self, panel: ControlPlanePanel) -> None:
        self.panels.append(panel)

    def snapshot(self) -> List[Dict[str, Any]]:
        return [panel.to_dict() for panel in self.panels]
