"""Tests for queue starvation scoring.

Covers QueueSample and StarvationScore.
"""

from uar.runtime.hardening.starvation import QueueSample, StarvationScore


class TestQueueSample:
    """QueueSample dataclass."""

    def test_creation(self):
        s = QueueSample(
            queue_name="q1", age_ms=100.0, depth=5, serviced_count=2
        )
        assert s.queue_name == "q1"
        assert s.age_ms == 100.0
        assert s.depth == 5
        assert s.serviced_count == 2


class TestStarvationScore:
    """StarvationScore computation."""

    def test_empty_samples(self):
        score = StarvationScore(samples=())
        assert score.worst_age_ms() == 0.0
        assert score.stalled_queues() == ()
        assert score.healthy() is True

    def test_worst_age(self):
        samples = (
            QueueSample("q1", 100.0, 1, 0),
            QueueSample("q2", 500.0, 2, 0),
        )
        score = StarvationScore(samples=samples)
        assert score.worst_age_ms() == 500.0

    def test_stalled_queues(self):
        samples = (
            QueueSample("q1", 10000.0, 1, 0),
            QueueSample("q2", 100.0, 0, 0),
            QueueSample("q3", 10000.0, 1, 5),
        )
        score = StarvationScore(samples=samples)
        stalled = score.stalled_queues()
        assert stalled == ("q1",)

    def test_healthy_true(self):
        samples = (
            QueueSample("q1", 100.0, 1, 1),
            QueueSample("q2", 100.0, 0, 0),
        )
        score = StarvationScore(samples=samples)
        assert score.healthy() is True

    def test_healthy_false(self):
        samples = (QueueSample("q1", 10000.0, 1, 0),)
        score = StarvationScore(samples=samples)
        assert score.healthy() is False

    def test_custom_max_age(self):
        samples = (QueueSample("q1", 3000.0, 1, 0),)
        score = StarvationScore(samples=samples)
        assert score.healthy(max_age_ms=2000.0) is False
        assert score.healthy(max_age_ms=5000.0) is True
