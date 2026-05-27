from uar.runtime.hardening.oscillation import OscillationScore


def test_stable_signal_scores_low() -> None:
    score = OscillationScore((1.0, 1.01, 1.0, 1.01, 1.0))

    assert score.normalized() < 0.25
    assert score.stable() is True


def test_unstable_signal_scores_high() -> None:
    score = OscillationScore((1.0, 10.0, -10.0, 12.0, -12.0))

    assert score.normalized() > 0.25
    assert score.stable() is False
