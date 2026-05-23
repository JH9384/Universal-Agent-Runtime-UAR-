from uar.core.events import (
    EVENT_SCHEMA_VERSION,
    RuntimeEvent,
    RuntimeEventType,
    emit_complete,
    emit_error,
    emit_skill_complete,
    emit_skill_start,
    emit_start,
    make_event,
)
from uar.core.replay import validate_runtime_event



def test_runtime_event_to_dict_roundtrip():
    event = RuntimeEvent(
        schema_version=EVENT_SCHEMA_VERSION,
        type="start",
        run_id="run-1",
        goal_id="goal-1",
        skill=None,
        timestamp=1.0,
        payload={"skills": ["alpha"]},
        error=None,
    )

    result = event.to_dict()

    assert result["schema_version"] == EVENT_SCHEMA_VERSION
    assert result["type"] == "start"
    assert result["payload"] == {"skills": ["alpha"]}



def test_make_event_produces_schema_valid_event():
    event = make_event(
        "start",
        run_id="run-1",
        goal_id="goal-1",
        timestamp=1.0,
    )

    validate_runtime_event(event)

    assert event["type"] == "start"



def test_make_event_accepts_runtime_event_type_enum():
    event = make_event(
        RuntimeEventType.SKILL_START,
        run_id="run-1",
        goal_id="goal-1",
        skill="alpha",
        timestamp=1.0,
    )

    validate_runtime_event(event)

    assert event["type"] == "skill_start"



def test_make_event_preserves_optional_metadata():
    event = make_event(
        RuntimeEventType.START,
        run_id="run-1",
        goal_id="goal-1",
        timestamp=1.0,
        metadata={"correlation_id": "corr-1"},
    )

    validate_runtime_event(event)

    assert event["correlation_id"] == "corr-1"



def test_emit_start_contains_skills():
    event = emit_start(
        run_id="run-1",
        goal_id="goal-1",
        skills=["alpha", "beta"],
        timestamp=1.0,
    )

    assert event["payload"]["skills"] == ["alpha", "beta"]



def test_emit_skill_events_are_schema_valid():
    start = emit_skill_start(
        run_id="run-1",
        goal_id="goal-1",
        skill="alpha",
        timestamp=2.0,
    )

    complete = emit_skill_complete(
        run_id="run-1",
        goal_id="goal-1",
        skill="alpha",
        result={"value": 42},
        timestamp=3.0,
    )

    validate_runtime_event(start)
    validate_runtime_event(complete)

    assert complete["payload"]["result"] == {"value": 42}



def test_emit_error_sets_error_payload_and_field():
    event = emit_error(
        run_id="run-1",
        goal_id="goal-1",
        error="boom",
        timestamp=4.0,
    )

    assert event["error"] == "boom"
    assert event["payload"]["error"] == "boom"



def test_emit_complete_contains_final_payload():
    event = emit_complete(
        run_id="run-1",
        goal_id="goal-1",
        status="completed",
        outputs=[{"result": "ok"}],
        final_context={"answer": 42},
        timestamp=5.0,
    )

    validate_runtime_event(event)

    assert event["payload"]["status"] == "completed"
    assert event["payload"]["final_context"] == {"answer": 42}
