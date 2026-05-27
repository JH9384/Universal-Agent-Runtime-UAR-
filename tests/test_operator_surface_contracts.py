from uar.core.operator_surface_contracts import OperatorSurfaceCard
from uar.core.operator_surface_contracts import OperatorSurfaceSnapshot


def test_operator_surface_snapshot_serialization():
    snapshot = OperatorSurfaceSnapshot(runtime_version="0.1.0")

    snapshot.add_card(
        OperatorSurfaceCard(
            title="Runtime Health",
            category="runtime.health",
            payload={"ok": True},
        )
    )

    payload = snapshot.to_dict()

    assert payload["runtime_version"] == "0.1.0"
    assert payload["cards"][0]["title"] == "Runtime Health"
    assert payload["cards"][0]["payload"]["ok"] is True
