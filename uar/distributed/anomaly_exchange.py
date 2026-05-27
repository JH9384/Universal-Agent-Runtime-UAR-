from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass(slots=True)
class AnomalyExchange:
    exchange_id: str
    anomaly_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, object]:
        return {
            "exchange_id": self.exchange_id,
            "anomaly_ids": list(self.anomaly_ids),
        }
