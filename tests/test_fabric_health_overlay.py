from uar.distributed.fabric_health import FabricHealth
from uar.distributed.fabric_health_overlay import FabricHealthOverlayBuilder


def test_fabric_health_overlay_builder() -> None:
    health = FabricHealth(
        synchronization_confidence=0.9,
        anomaly_count=1,
        missing_replays=1,
        repair_backlog=0,
    )

    overlay = FabricHealthOverlayBuilder().build(
        overlay_id="overlay-1",
        health=health,
    )

    payload = overlay.to_dict()

    assert payload["overall_score"] > 0.0
    assert "anomaly-pressure" in payload["indicators"]
