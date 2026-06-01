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


def test_missing_run_id_generates_store_record_missing_warning():
    record = RunRecord(
        run_id="",
        goal_id="goal-1",
        skills=["alpha"],
        outputs=["ok"],
        events=[
            _event("start", run_id="", timestamp=1.0),
            _event("complete", run_id="", timestamp=2.0,
                   payload={"status": "success"}),
        ],
    )
    report = score_replay(record)
    assert any(w.code == "store_record_missing" for w in report.warnings)
    assert report.dimensions["store_consistency"] < 100


def test_no_artifacts_generates_artifact_missing_warning():
    record = RunRecord(
        run_id="run-no-artifacts",
        goal_id="goal-1",
        skills=["alpha"],
        outputs=[],
        final_context=None,
        uor_address=None,
        uor_witness=None,
        events=[
            _event("start", run_id="run-no-artifacts", timestamp=1.0,
                   payload={"skills": ["alpha"]}),
            _event(
                "complete",
                run_id="run-no-artifacts",
                timestamp=2.0,
                payload={
                    "status": "success",
                    "outputs": [],
                    "errors": [],
                    "final_context": {},
                },
            ),
        ],
    )
    report = score_replay(record)
    w = next(
        (w for w in report.warnings if w.code == "artifact_missing"), None
    )
    assert w is not None, "expected artifact_missing warning"
    assert w.severity == "warning"
    assert report.dimensions["artifact_completeness"] == 0


def test_store_consistency_coerces_event_run_id_to_str():
    """Event run_id that is an int must not produce false-positive mismatch.

    Regression: ev.get('run_id') != record.run_id compared int vs str,
    causing a spurious store_event_mismatch warning.
    """
    record = RunRecord(
        run_id="123",
        goal_id="goal-1",
        skills=["alpha"],
        outputs=["ok"],
        events=[
            {
                "schema_version": "uar.event.v1",
                "type": "start",
                "run_id": 123,  # integer, not string
                "goal_id": "goal-1",
                "timestamp": 1.0,
                "payload": {},
                "error": None,
            },
        ],
    )
    report = score_replay(record)
    assert not any(
        w.code == "store_event_mismatch" for w in report.warnings
    ), "int run_id should be coerced to str before comparison"
    assert report.dimensions["store_consistency"] == 100
