from uar.core.replay_restore_point import ReplayRestorePoint
from uar.core.replay_restoration import ReplayRestoration


def test_replay_restoration_roundtrip():
    restoration = ReplayRestoration()

    restore_point = ReplayRestorePoint(
        replay_id="replay-restore-001",
        snapshot_id="snapshot-001",
        lineage=["root", "replay-restore-001"],
        metadata={"mode": "deterministic_replay"},
    )

    result = restoration.restore(restore_point)

    payload = result.to_dict()

    assert payload["restored"] is True
    assert payload["restore_point"]["snapshot_id"] == "snapshot-001"
