from uar.core.replay_index import ReplayIndex
from uar.core.replay_index import ReplayIndexEntry


def test_replay_index_tracks_parents():
    replay_index = ReplayIndex()

    entry = ReplayIndexEntry(
        replay_id="replay-002",
        certificate_hash="abc123",
        parent_ids=["replay-001"],
    )

    replay_index.add(entry)

    assert replay_index.get("replay-002") is not None
    assert replay_index.parents("replay-002") == ["replay-001"]
