from uar.core.live_replay_engine import LiveReplayEngine


def test_live_replay_engine_accepts_matching_trace():
    engine = LiveReplayEngine()

    baseline = engine.create_trace("baseline")
    baseline.append({"event": "start"})

    candidate = engine.create_trace("baseline")
    candidate.append({"event": "start"})

    result = engine.verify(baseline, candidate)

    assert result.accepted is True
    assert result.divergence_index is None


def test_live_replay_engine_detects_divergence():
    engine = LiveReplayEngine()

    baseline = engine.create_trace("baseline")
    baseline.append({"event": "start"})

    candidate = engine.create_trace("candidate")
    candidate.append({"event": "different"})

    result = engine.verify(baseline, candidate)

    assert result.accepted is False
    assert result.divergence_index == 0
