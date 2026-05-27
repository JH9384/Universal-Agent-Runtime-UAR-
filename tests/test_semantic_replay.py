from uar.core.semantic_replay import SemanticReplayNormalizer
from uar.core.semantic_replay import SemanticReplayRecord


def test_semantic_replay_normalization():
    normalizer = SemanticReplayNormalizer()

    result = normalizer.normalize("  Runtime   Replay  ")

    assert result == "runtime replay"


def test_semantic_replay_record_serialization():
    record = SemanticReplayRecord(
        replay_id="replay-001",
        canonical_form="runtime replay",
    )

    payload = record.to_dict()

    assert payload["replay_id"] == "replay-001"
    assert payload["canonical_form"] == "runtime replay"
