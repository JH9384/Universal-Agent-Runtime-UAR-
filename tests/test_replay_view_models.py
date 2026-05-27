from uar.core.replay_view_models import ReplayTimelineNode
from uar.core.replay_view_models import ReplayTimelineView


def test_replay_timeline_view_serialization():
    view = ReplayTimelineView()

    view.add_node(
        ReplayTimelineNode(
            replay_id="replay-001",
            status="restored",
            related=["replay-000"],
        )
    )

    payload = view.to_dict()

    assert payload["nodes"][0]["replay_id"] == "replay-001"
    assert payload["nodes"][0]["status"] == "restored"
