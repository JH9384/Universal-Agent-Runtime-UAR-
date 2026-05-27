from uar.distributed.fabric_forecasting import FabricForecastEngine


def test_fabric_forecast_engine() -> None:
    forecast = FabricForecastEngine().forecast(
        forecast_id="forecast-1",
        current_health=0.9,
        anomaly_count=2,
    )

    payload = forecast.to_dict()

    assert payload["projected_health"] < 0.9
    assert payload["projected_anomalies"] == 2
