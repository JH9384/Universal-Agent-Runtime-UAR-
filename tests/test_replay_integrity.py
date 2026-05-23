import pytest

from uar.core.exceptions import EventContractError
from uar.core.replay import (
    EVENT_SCHEMA_VERSION,
    replay_summary,
    run_record_from_events,
    validate_event_stream,
)


def event(
    event_type,
    *,
    run_id="run-1",
    goal_id="goal-1",
    skill=None,
    timestamp=1.0,
    payload=None,
    error=None,
):
    return {
        "schema_version": EVENT_SCHEMA_VERSION,
        "type": event_type,
        "run_id": run_id,
        "goal_id": goal_id,
        "skill": skill,
        "timestamp": timestamp,
        "payload": payload or {},
        "error": error,
    }


def completed_events():
    return [
        event("start", timestamp=1.0, payload={"skills": ["alpha"]}),
        event("skill_start", skill="alpha", timestamp=2.0),
        event(
            "skill_complete",
            skill="alpha",
            timestamp=3.0,
            payload={"result": "ok"},
        ),
        event(
            "complete",
            timestamp=4.0,
            payload={
                "status": "completed",
                "outputs": [{"result": "ok"}],
                "errors": [],
                "final_context": {"answer": 42},
            },
        ),
    ]


def test_validate_event_stream_preserves_order():
    events = completed_events()

    validated = validate_event_stream(events)

    assert validated == events
    assert [item["type"] for item in validated] == [
        "start",
        "skill_start",
        "skill_complete",
        "complete",
    ]


def test_run_record_from_events_is_deterministic():
    events = completed_events()

    record_a = run_record_from_events(events)
    record_b = run_record_from_events(events)

    assert record_a == record_b
    assert record_a.status == "completed"
    assert record_a.skills == ["alpha"]
    assert record_a.outputs == [{"result": "ok"}]
    assert record_a.final_context == {"answer": 42}


def test_replay_summary_is_stable():
    record = run_record_from_events(completed_events())

    assert replay_summary(record) == {
        "run_id": "run-1",
        "goal_id": "goal-1",
        "status": "completed",
        "skill_count": 1,
        "event_count": 4,
        "errors": [],
        "outputs": [{"result": "ok"}],
    }


def test_empty_event_stream_rejected():
    with pytest.raises(EventContractError, match="empty event stream"):
        validate_event_stream([])


def test_missing_required_event_key_rejected():
    events = completed_events()
    del events[0]["schema_version"]

    with pytest.raises(EventContractError, match="missing keys"):
        validate_event_stream(events)


def test_wrong_schema_version_rejected():
    events = completed_events()
    events[0]["schema_version"] = "uar.event.v0"

    with pytest.raises(EventContractError, match="Unsupported"):
        validate_event_stream(events)


def test_stream_must_start_with_start_event():
    events = completed_events()[1:]

    with pytest.raises(EventContractError, match="start with a start event"):
        validate_event_stream(events)


def test_stream_must_end_with_complete_event():
    events = completed_events()[:-1]

    with pytest.raises(EventContractError, match="end with a complete event"):
        validate_event_stream(events)


def test_stream_rejects_mixed_run_ids():
    events = completed_events()
    events[1]["run_id"] = "run-2"

    with pytest.raises(EventContractError, match="multiple run_ids"):
        validate_event_stream(events)


def test_stream_rejects_mixed_goal_ids():
    events = completed_events()
    events[1]["goal_id"] = "goal-2"

    with pytest.raises(EventContractError, match="multiple goal_ids"):
        validate_event_stream(events)
