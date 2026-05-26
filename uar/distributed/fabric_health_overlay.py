from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List

from uar.distributed.fabric_health import FabricHealth


@dataclass(slots=True)
class FabricHealthOverlay:
    overlay_id: str
    overall_score: float
    indicators: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "overlay_id": self.overlay_id,
            "overall_score": self.overall_score,
            "indicators": list(self.indicators),
        }


class FabricHealthOverlayBuilder:
    def build(self, overlay_id: str, health: FabricHealth) -> FabricHealthOverlay:
        indicators: List[str] = []
        if health.anomaly_count > 0:
            indicators.append("anomaly-pressure")
        if health.missing_replays > 0:
            indicators.append("replay-gap")
        if health.repair_backlog > 0:
            indicators.append("repair-backlog")

        return FabricHealthOverlay(
            overlay_id=overlay_id,
            overall_score=health.overall_score(),
            indicators=indicators,
        )
