from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass(slots=True)
class GovernanceHeatmapCell:
    region: str
    pressure: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "region": self.region,
            "pressure": self.pressure,
        }


class GovernanceHeatmap:
    def __init__(self) -> None:
        self.cells: List[GovernanceHeatmapCell] = []

    def add_cell(self, cell: GovernanceHeatmapCell) -> None:
        self.cells.append(cell)

    def snapshot(self) -> List[Dict[str, object]]:
        return [cell.to_dict() for cell in self.cells]
