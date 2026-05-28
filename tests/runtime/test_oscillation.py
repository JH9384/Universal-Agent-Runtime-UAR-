"""Tests for oscillation scoring helpers.

Covers OscillationScore computation.
"""

from uar.runtime.hardening.oscillation import OscillationScore


class TestOscillationScore:
    """OscillationScore dataclass."""

    def test_empty_samples(self):
        score = OscillationScore(samples=())
        assert score.amplitude() == 0.0
        assert score.direction_changes() == 0
        assert score.normalized() == 0.0
        assert score.stable() is True

    def test_single_sample(self):
        score = OscillationScore(samples=(5.0,))
        assert score.amplitude() == 0.0
        assert score.direction_changes() == 0
        assert score.normalized() == 0.0
        assert score.stable() is True

    def test_amplitude(self):
        score = OscillationScore(samples=(1.0, 5.0, 3.0))
        assert score.amplitude() == 4.0

    def test_direction_changes(self):
        score = OscillationScore(samples=(1.0, 3.0, 2.0, 4.0, 3.0))
        assert score.direction_changes() == 3

    def test_no_direction_changes(self):
        score = OscillationScore(samples=(1.0, 2.0, 3.0, 4.0))
        assert score.direction_changes() == 0

    def test_normalized_stable(self):
        score = OscillationScore(samples=(10.0, 10.1, 10.0, 10.1))
        assert score.normalized() < 0.25
        assert score.stable() is True

    def test_normalized_unstable(self):
        score = OscillationScore(samples=(0.0, 100.0, 0.0, 100.0))
        assert score.normalized() > 0.25
        assert score.stable() is False

    def test_custom_threshold(self):
        score = OscillationScore(samples=(0.0, 10.0, 0.0))
        assert score.stable(threshold=0.5) is False
        assert score.stable(threshold=2.0) is True

    def test_flat_line(self):
        score = OscillationScore(samples=(5.0, 5.0, 5.0))
        assert score.amplitude() == 0.0
        assert score.direction_changes() == 0
        assert score.normalized() == 0.0
