from uar.core.replay_recovery import ReplayRecovery
from uar.core.replay_restore_point import ReplayRestorePoint


def test_replay_recovery_restores_continuity():
    recovery = ReplayRecovery()

    restore_point = ReplayRestorePoint(
        replay_id="replay-900",
        snapshot_id="snapshot-900",
        lineage=["root", "replay-900"],
    )

    result = recovery.recover(restore_point)

    payload = result.to_dict()

    assert payload["recovered"] is True
    assert payload["snapshot_id"] == "snapshot-900"
