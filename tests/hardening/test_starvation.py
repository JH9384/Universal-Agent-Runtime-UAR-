from uar.runtime.hardening.starvation import QueueSample, StarvationScore


def test_detects_stalled_queues() -> None:
    score = StarvationScore(
        (
            QueueSample("runtime", 10_000, 20, 0),
            QueueSample("observer", 100, 5, 5),
        )
    )

    assert score.healthy() is False
    assert "runtime" in score.stalled_queues()


def test_healthy_queues_pass() -> None:
    score = StarvationScore(
        (
            QueueSample("runtime", 100, 10, 10),
        )
    )

    assert score.healthy() is True
