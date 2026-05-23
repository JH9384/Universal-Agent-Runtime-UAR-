from uar.core.timeline import project_timeline, summarize_timeline



def build_events():
    return [
        {
            "type": "start",
            "timestamp": 1.0,
            "skill": None,
            "payload": {},
            "error": None,
        },
        {
            "type": "skill_start",
            "timestamp": 2.0,
            "skill": "alpha",
            "payload": {},
            "error": None,
        },
        {
            "type": "skill_complete",
            "timestamp": 3.0,
            "skill": "alpha",
            "payload": {"result": 42},
            "error": None,
        },
        {
            "type": "metrics",
            "timestamp": 4.0,
            "skill": None,
            "payload": {"total_time_sec": 1.2},
            "error": None,
        },
        {
            "type": "complete",
            "timestamp": 5.0,
            "skill": None,
            "payload": {"status": "completed"},
            "error": None,
        },
    ]



def test_project_timeline_preserves_order():
    timeline = project_timeline(build_events())

    assert [event["type"] for event in timeline] == [
        "start",
        "skill_start",
        "skill_complete",
        "metrics",
        "complete",
    ]



def test_project_timeline_adds_indices():
    timeline = project_timeline(build_events())

    assert timeline[0]["index"] == 0
    assert timeline[-1]["index"] == 4



def test_project_timeline_ignores_unknown_events():
    events = build_events() + [
        {
            "type": "unknown",
            "timestamp": 6.0,
            "payload": {},
        }
    ]

    timeline = project_timeline(events)

    assert len(timeline) == 5



def test_timeline_summary_counts_events():
    summary = summarize_timeline(project_timeline(build_events()))

    assert summary == {
        "event_count": 5,
        "skill_starts": 1,
        "skill_completes": 1,
        "failures": 0,
    }
