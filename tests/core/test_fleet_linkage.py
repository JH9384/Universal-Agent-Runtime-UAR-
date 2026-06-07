"""Tests for D4C fleet signal linkage helpers."""

from uar.core.fleet_linkage import (
    attach_linkage_to_fleet_summary,
    build_fleet_signal_linkage,
)


def test_build_fleet_signal_linkage_handles_missing_signal():
    linkage = build_fleet_signal_linkage(None)

    assert linkage["has_signal"] is False
    assert linkage["replay"] is None
    assert linkage["incidents"] == []
    assert linkage["recommendations"] == []
    assert linkage["evidence_refs"] == []


def test_build_fleet_signal_linkage_exposes_existing_ids():
    signal = {
        "id": "fleet:service:svc-a",
        "scope": "service",
        "level": "critical",
        "latest_run_id": "run-1",
        "linked_incident_ids": ["inc-1", "inc-2"],
        "linked_recommendation_ids": ["rec-1"],
        "evidence_refs": ["run:run-1"],
    }

    linkage = build_fleet_signal_linkage(signal)

    assert linkage["has_signal"] is True
    assert linkage["signal_id"] == "fleet:service:svc-a"
    assert linkage["scope"] == "service"
    assert linkage["level"] == "critical"
    assert linkage["replay"] == {"run_id": "run-1", "available": True}
    assert linkage["incidents"] == ["inc-1", "inc-2"]
    assert linkage["recommendations"] == ["rec-1"]
    assert linkage["evidence_refs"] == ["run:run-1"]


def test_build_fleet_signal_linkage_marks_replay_unavailable_without_run():
    signal = {
        "id": "fleet:fleet:default",
        "scope": "fleet",
        "level": "warning",
        "latest_run_id": None,
    }

    linkage = build_fleet_signal_linkage(signal)

    assert linkage["replay"] == {"run_id": None, "available": False}


def test_attach_linkage_to_fleet_summary_copies_top_and_signal_list():
    original = {
        "status": "critical",
        "top_signal": {
            "id": "fleet:skill:parse_pdf",
            "scope": "skill",
            "level": "critical",
            "latest_run_id": "run-2",
            "linked_incident_ids": ["inc-3"],
        },
        "signals": [
            {
                "id": "fleet:skill:parse_pdf",
                "scope": "skill",
                "level": "critical",
                "latest_run_id": "run-2",
            }
        ],
    }

    enriched = attach_linkage_to_fleet_summary(original)

    assert "linkage" not in original["top_signal"]
    assert enriched is not original
    assert enriched["top_signal"]["linkage"]["replay"]["run_id"] == "run-2"
    assert enriched["top_signal"]["linkage"]["incidents"] == ["inc-3"]
    assert enriched["signals"][0]["linkage"]["replay"]["available"] is True
