from uar.core.contracts import RunRecord
from uar.core.structure import events_to_markdown, events_to_structure, run_record_to_markdown


def sample_events():
    return [
        {
            "schema_version": "uar.event.v1",
            "type": "orchestration_plan",
            "run_id": "pending",
            "goal_id": "goal-1",
            "skill": None,
            "timestamp": 0,
            "payload": {
                "graph": {
                    "nodes": [
                        {"id": "skill-1-section_sum", "skill": "section_sum", "depends_on": []},
                        {"id": "skill-2-sum_review", "skill": "sum_review", "depends_on": ["skill-1-section_sum"]},
                    ],
                    "edges": [{"from": "skill-1-section_sum", "to": "skill-2-sum_review"}],
                }
            },
            "error": None,
        },
        {
            "schema_version": "uar.event.v1",
            "type": "start",
            "run_id": "run-1",
            "goal_id": "goal-1",
            "skill": None,
            "timestamp": 1,
            "payload": {"goal": "Say hello", "skills": ["section_sum"]},
            "error": None,
        },
        {
            "schema_version": "uar.event.v1",
            "type": "skill_complete",
            "run_id": "run-1",
            "goal_id": "goal-1",
            "skill": "section_sum",
            "timestamp": 2,
            "payload": {"result": {"summary": "hello"}},
            "error": None,
        },
        {
            "schema_version": "uar.event.v1",
            "type": "complete",
            "run_id": "run-1",
            "goal_id": "goal-1",
            "skill": None,
            "timestamp": 3,
            "payload": {"status": "completed", "outputs": [{"section_sum": {"summary": "hello"}}], "errors": []},
            "error": None,
        },
    ]


def test_events_to_structure_contains_core_sections():
    root = events_to_structure(sample_events())
    assert root.title == "UAR Run"
    titles = [child.title for child in root.children]
    assert "Goal" in titles
    assert "Execution Plan" in titles
    assert "Events" in titles
    assert "Status" in titles
    assert "Outputs" in titles


def test_events_to_markdown_is_tool_agnostic_and_human_readable():
    markdown = events_to_markdown(sample_events())
    assert markdown.startswith("# UAR Run")
    assert "## Goal" in markdown
    assert "Say hello" in markdown
    assert "## Execution Plan" in markdown
    assert "section_sum" in markdown
    assert "## Outputs" in markdown


def test_run_record_to_markdown_uses_events_as_source_of_truth():
    record = RunRecord(
        run_id="run-1",
        goal_id="goal-1",
        skills=["section_sum"],
        status="completed",
        events=sample_events(),
    )
    markdown = run_record_to_markdown(record)
    assert "# UAR Run" in markdown
    assert "completed" in markdown
