import json
from pathlib import Path

from uar.core.replay import replay_summary, run_record_from_events, validate_event_stream
from uar.core.timeline import project_timeline, summarize_timeline

FIXTURE_DIR = Path(__file__).parent / "fixtures"



def load_fixture(name: str):
    return json.loads((FIXTURE_DIR / name).read_text())



def test_success_fixture_reconstructs_completed_run_record():
    events = load_fixture("runtime_trace_success.json")

    validated = validate_event_stream(events)
    record = run_record_from_events(validated)

    assert record.status == "completed"
    assert record.goal_id == "goal-fixture-success"
    assert record.run_id == "run-fixture-success"
    assert record.errors == []
    assert len(record.outputs) == 1



def test_success_fixture_projects_stable_timeline():
    events = load_fixture("runtime_trace_success.json")

    timeline = project_timeline(events)
    summary = summarize_timeline(timeline)

    assert [event["type"] for event in timeline] == [
        "start",
        "skill_start",
        "skill_complete",
        "metrics",
        "complete",
    ]

    assert summary == {
        "event_count": 5,
        "skill_starts": 1,
        "skill_completes": 1,
        "failures": 0,
    }



def test_failure_fixture_reconstructs_failed_run_record():
    events = load_fixture("runtime_trace_failure.json")

    validated = validate_event_stream(events)
    record = run_record_from_events(validated)

    assert record.status == "failed"
    assert record.goal_id == "goal-fixture-failure"
    assert record.errors == ["Fixture execution failure"]



def test_failure_fixture_projects_failure_timeline():
    events = load_fixture("runtime_trace_failure.json")

    timeline = project_timeline(events)
    summary = summarize_timeline(timeline)

    assert [event["type"] for event in timeline] == [
        "start",
        "skill_start",
        "skill_failed",
        "complete",
    ]

    assert summary == {
        "event_count": 4,
        "skill_starts": 1,
        "skill_completes": 0,
        "failures": 1,
    }



def test_success_fixture_replay_summary_is_stable():
    events = load_fixture("runtime_trace_success.json")

    record = run_record_from_events(events)

    assert replay_summary(record) == {
        "run_id": "run-fixture-success",
        "goal_id": "goal-fixture-success",
        "status": "completed",
        "skill_count": 1,
        "event_count": 5,
        "errors": [],
        "outputs": [
            {
                "section_sum": {
                    "summary": "Fixture completed successfully."
                }
            }
        ],
    }
