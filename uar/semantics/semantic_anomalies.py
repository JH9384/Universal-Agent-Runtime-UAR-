from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class SemanticAnomaly:
    anomaly_id: str
    category: str
    severity: float

    def to_dict(self) -> Dict[str, object]:
        return {
            "anomaly_id": self.anomaly_id,
            "category": self.category,
            "severity": self.severity,
        }


class SemanticAnomalyAnalyzer:
    def analyze(self, drift_score: float) -> SemanticAnomaly:
        category = "stable" if drift_score < 0.5 else "divergent"
        return SemanticAnomaly(
            anomaly_id=f"anomaly-{int(drift_score * 1000)}",
            category=category,
            severity=drift_score,
        )
