from uar.core.contracts import RunRecord
from uar.core.replay_confidence import confidence_tier, score_replay


def _event(event_type: str, run_id: str = "run-1", goal_id: str = "goal-1", skill: str | None = None, timestamp: float = 1.0, payload: dict | None = None, error: str | None = None) -> dict:
    return {
        "schema_version": "uar.event.v1",
        "type": event_type,
        "run_id": run_id,
        "goal_id": goal_id,
        "skill": skill,
        "timestamp": timestamp,
        "payload": payload or {},
        "error": error,
    }


def _verified_record() -> RunRecord:
    events = [
        _event("start", timestamp=1.0, payload={"skills": ["alpha"]}),
        _event("skill_start", skill="alpha", timestamp=2.0),
        _event("skill_complete", skill="alpha", timestamp=3.0),
        _event("complete", timestamp=4.0, payload={"status": "success", "outputs": ["ok"], "errors": [], "final_context": {"done": True}}),
    ]
    return RunRecord(
        run_id="run-1",
        goal_id="goal-1",
        skills=["alpha"],
        outputs=["ok"],
        status="success",
        events=events,
        final_context={"done": True},
    )


def test_confidence_tier_boundaries():
    assert confidence_tier(100) == "Verified"
    assert confidence_tier(95) == "Verified"
    assert confidence_tier(94) == "High"
    assert confidence_tier(85) == "High"
    assert confidence_tier(84) == "Medium"
    assert confidence_tier(70) == "Medium"
    assert confidence_tier(69) == "Low"
    assert confidence_tier(50) == "Low"
    assert confidence_tier(49) == "Failed"


def test_verified_replay_scores_highest_tier():
    report = score_replay(_verified_record())
    assert report.score == 100
    assert report.tier == "Verified"
    assert report.errors == []
    assert report.to_dict()["confidence"]["score"] == 100


def test_missing_events_fails_confidence():
    record = RunRecord(run_id="run-empty", goal_id="goal-1", skills=[])
    report = score_replay(record)
    assert report.tier == "Failed"
    assert report.dimensions["event_completeness"] == 0
    assert any(w.code == "missing_events" for w in report.warnings)


def test_legacy_event_shape_degrades_gracefully():
    record = RunRecord(
        run_id="run-legacy",
        goal_id="goal-legacy",
        skills=["legacy"],
        outputs=["ok"],
        events=[
            {"type": "start", "payload": {"skills": ["legacy"]}},
            {"type": "complete", "payload": {"status": "success", "outputs": ["ok"]}},
        ],
    )
    report = score_replay(record)
    assert report.score > 0
    assert any(w.code == "legacy_event_shape" for w in report.warnings)
    assert any(w.code == "partial_replay" for w in report.warnings)


def test_store_event_mismatch_generates_warning():
    record = _verified_record()
    record.events[0]["run_id"] = "other-run"
    report = score_replay(record)
    assert report.score < 100
    assert any(w.code == "store_event_mismatch" for w in report.warnings)


def test_invalid_event_stream_generates_reconstruction_warning():
    record = _verified_record()
    record.events[-1]["type"] = "not-complete"
    report = score_replay(record)
    assert report.score < 100
    assert any(w.code == "invalid_event_schema" for w in report.warnings)
    assert any(w.code == "reconstruction_failed" for w in report.warnings)
