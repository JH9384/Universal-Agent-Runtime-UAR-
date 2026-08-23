"""Tests for D4C Operator Daily Briefing composer."""

from uar.core.operator_daily_briefing import (
    build_operator_daily_briefing,
    build_operator_daily_briefing_from_records,
)


def _mission_control(fleet_status="nominal", top_signal=None):
    return {
        "fleet_summary": {
            "status": fleet_status,
            "active_signals": 1 if top_signal else 0,
            "top_signal": top_signal,
        },
        "runtime_health": {"score": 95, "tier": "Healthy"},
        "certification": {"score": 90, "level": "Gold"},
        "trust_summary": {"top_trusted": "cache", "top_trust_score": 0.82},
        "recent_warnings": [],
    }


def test_daily_briefing_nominal_adds_monitor_action():
    briefing = build_operator_daily_briefing(_mission_control(), generated_at=1.0)

    assert briefing["generated_at"] == 1.0
    assert briefing["summary"]["priority"] == "nominal"
    assert briefing["summary"]["fleet_status"] == "nominal"
    assert briefing["next_actions"][0]["id"] == "monitor"


def test_daily_briefing_top_signal_adds_inspect_replay_and_outcome_actions():
    top_signal = {
        "id": "fleet:service:svc-a",
        "level": "critical",
        "message": "3 failures",
        "linkage": {
            "replay": {"run_id": "run-1", "available": True},
            "recommendations": ["rec-1"],
        },
    }

    briefing = build_operator_daily_briefing(
        _mission_control("critical", top_signal), generated_at=2.0
    )

    action_ids = [a["id"] for a in briefing["next_actions"]]
    assert briefing["summary"]["priority"] == "critical"
    assert "inspect_top_fleet_signal" in action_ids
    assert "open_replay" in action_ids
    assert "record_outcome" in action_ids
    assert briefing["next_actions"][1]["run_id"] == "run-1"


def test_daily_briefing_from_records_includes_evidence_pack_preview():
    records = [
        {
            "run_id": "run-brief-1",
            "goal_id": "g1",
            "status": "failed",
            "skills": ["echo"],
            "metadata": {"service": "svc-brief"},
            "created_at": 100.0,
        }
    ]

    briefing = build_operator_daily_briefing_from_records(
        _mission_control(), records, generated_at=3.0
    )

    assert briefing["evidence_pack"]["available"] is True
    assert briefing["evidence_pack"]["section_count"] == 3
    assert "Fleet Signal Evidence" in briefing["evidence_pack"]["markdown_preview"]
    assert "Incident Intelligence Evidence" in briefing["evidence_pack"]["markdown_preview"]
    assert "Recurrence Correlation Evidence" in briefing["evidence_pack"]["markdown_preview"]
    assert any(a["id"] == "generate_evidence_pack" for a in briefing["next_actions"])
