"""Tests for D4C reusable fleet signal builder."""

from uar.core.fleet_signals import build_fleet_signals, build_fleet_summary


def test_build_fleet_signals_groups_failures_by_service():
    records = [
        {
            "run_id": "r1",
            "goal_id": "g1",
            "status": "failed",
            "errors": ["boom"],
            "skills": ["echo"],
            "metadata": {"service": "svc-a"},
            "created_at": 100.0,
        },
        {
            "run_id": "r2",
            "goal_id": "g1",
            "status": "failed",
            "errors": ["boom again"],
            "skills": ["echo"],
            "metadata": {"service": "svc-a"},
            "created_at": 200.0,
        },
    ]

    signals = build_fleet_signals(records, now=300.0)

    assert len(signals) == 1
    sig = signals[0]
    assert sig.scope == "service"
    assert sig.title == "Service signal: svc-a"
    assert sig.affected_run_ids == ["r2", "r1"]
    assert sig.latest_run_id == "r2"
    assert sig.count == 2
    assert sig.failure_rate == 1.0
    assert sig.level == "critical"


def test_build_fleet_signals_uses_skill_fallback_without_metadata():
    records = [
        {
            "run_id": "r1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["parse_pdf"],
            "metadata": {},
            "created_at": 100.0,
        }
    ]

    signals = build_fleet_signals(records)

    assert len(signals) == 1
    assert signals[0].scope == "skill"
    assert signals[0].title == "Skill signal: parse_pdf"
    assert signals[0].latest_run_id == "r1"


def test_build_fleet_signals_carries_incident_recommendation_and_evidence_refs():
    records = [
        {
            "run_id": "r1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {
                "node_id": "node-1",
                "incident_id": "inc-1",
                "recommendation_id": "rec-1",
                "replay_confidence": 0.8,
            },
            "created_at": 100.0,
        },
        {
            "run_id": "r2",
            "goal_id": "g1",
            "status": "warning",
            "skills": ["echo"],
            "metadata": {
                "node_id": "node-1",
                "incident_ids": ["inc-1", "inc-2"],
                "recommendation_ids": ["rec-1", "rec-2"],
                "replay_confidence": 0.6,
            },
            "created_at": 200.0,
        },
    ]

    signals = build_fleet_signals(records)
    sig = signals[0]

    assert sig.linked_incident_ids == ["inc-1", "inc-2"]
    assert sig.linked_recommendation_ids == ["rec-1", "rec-2"]
    assert sig.replay_confidence == 0.7
    assert sig.evidence_refs == ["run:r2", "run:r1"]


def test_build_fleet_summary_returns_nominal_when_no_signals():
    summary = build_fleet_summary([])

    assert summary["status"] == "nominal"
    assert summary["active_signals"] == 0
    assert summary["critical_signals"] == 0
    assert summary["warning_signals"] == 0
    assert summary["top_signal"] is None
    assert summary["signals"] == []


def test_build_fleet_summary_prioritizes_critical_top_signal():
    records = [
        {
            "run_id": "warn",
            "goal_id": "g1",
            "status": "warning",
            "skills": ["warn_skill"],
            "created_at": 100.0,
        },
        {
            "run_id": "fail1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["fail_skill"],
            "created_at": 200.0,
        },
    ]

    signals = build_fleet_signals(records)
    summary = build_fleet_summary(signals)

    assert summary["active_signals"] == 2
    assert summary["critical_signals"] == 1
    assert summary["warning_signals"] == 1
    assert summary["status"] == "critical"
    assert summary["top_signal"]["level"] == "critical"
    assert summary["top_signal"]["latest_run_id"] == "fail1"
