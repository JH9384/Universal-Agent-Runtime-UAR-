from uar.runtime.hardening.replay_score import ReplayScore


def test_replay_score_detects_divergence() -> None:
    score = ReplayScore(
        total_events=100,
        missing_events=1,
        duplicate_events=1,
        out_of_order_events=1,
        invalid_events=1,
    )

    assert score.divergence() == 0.04
    assert score.confidence() == 0.96
    assert score.passes(minimum_confidence=0.95) is True


def test_empty_replay_is_safe() -> None:
    score = ReplayScore(total_events=0)

    assert score.divergence() == 0.0
    assert score.confidence() == 1.0
