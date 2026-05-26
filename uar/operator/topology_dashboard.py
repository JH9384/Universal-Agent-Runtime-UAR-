from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class TopologyDashboard:
    dashboard_id: str
    node_count: int
    relationship_count: int
    active_anomalies: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "dashboard_id": self.dashboard_id,
            "node_count": self.node_count,
            "relationship_count": self.relationship_count,
            "active_anomalies": list(self.active_anomalies),
        }
