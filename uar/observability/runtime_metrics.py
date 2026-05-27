from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict


@dataclass(slots=True)
class RuntimeMetric:
    name: str
    value: float

    def to_dict(self) -> Dict[str, float]:
        return {
            "value": self.value,
        }


class RuntimeMetricsRegistry:
    def __init__(self) -> None:
        self.metrics: Dict[str, RuntimeMetric] = {}

    def put(self, metric: RuntimeMetric) -> None:
        self.metrics[metric.name] = metric

    def snapshot(self) -> Dict[str, object]:
        return {
            key: metric.to_dict()
            for key, metric in self.metrics.items()
        }
