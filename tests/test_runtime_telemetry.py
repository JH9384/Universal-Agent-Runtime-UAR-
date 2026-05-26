from uar.core.runtime_telemetry import RuntimeTelemetryBuffer


def test_runtime_telemetry_snapshot():
    telemetry = RuntimeTelemetryBuffer()

    telemetry.emit(
        "runtime.ingress",
        {"replay_safe": True},
    )

    snapshot = telemetry.snapshot()

    assert len(snapshot) == 1
    assert snapshot[0]["category"] == "runtime.ingress"
