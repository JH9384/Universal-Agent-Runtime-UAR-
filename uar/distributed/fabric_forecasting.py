from __future__ import annotations

from dataclasses import dataclass
from typing import Dict


@dataclass(slots=True)
class FabricForecast:
    forecast_id: str
    projected_health: float
    projected_anomalies: int

    def to_dict(self) -> Dict[str, object]:
        return {
            "forecast_id": self.forecast_id,
            "projected_health": self.projected_health,
            "projected_anomalies": self.projected_anomalies,
        }


class FabricForecastEngine:
    def forecast(self, forecast_id: str, current_health: float, anomaly_count: int) -> FabricForecast:
        projected_health = max(0.0, current_health - (anomaly_count * 0.05))
        return FabricForecast(
            forecast_id=forecast_id,
            projected_health=projected_health,
            projected_anomalies=anomaly_count,
        )
