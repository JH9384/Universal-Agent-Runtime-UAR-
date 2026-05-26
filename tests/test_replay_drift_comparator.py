from uar.core.replay_drift_comparator import ReplayDriftComparator


def test_replay_drift_detection():
    comparator = ReplayDriftComparator()

    result = comparator.compare(
        topology_a="A",
        topology_b="B",
        semantic_a="same",
        semantic_b="same",
        governance_a="X",
        governance_b="Y",
    )

    assert result.topology_drift == 1.0
    assert result.semantic_drift == 0.0
    assert result.governance_drift == 1.0
    assert result.total_drift > 0.0
