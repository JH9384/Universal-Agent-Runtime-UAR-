from uar.core.control_plane import ControlPlanePanel
from uar.core.control_plane import RuntimeControlPlane


def test_control_plane_snapshot():
    plane = RuntimeControlPlane()

    plane.add_panel(
        ControlPlanePanel(
            name="replay_timeline",
            status="active",
        )
    )

    snapshot = plane.snapshot()

    assert len(snapshot) == 1
    assert snapshot[0]["name"] == "replay_timeline"
