"""Tests for D4C fleet alert adapter."""

from uar.core.fleet_alerts import (
    fleet_alert_from_summary,
    merge_alerts_with_fleet,
)


def test_fleet_alert_from_summary_returns_none_without_top_signal():
    assert fleet_alert_from_summary(None) is None
    assert fleet_alert_from_summary({"top_signal": None}) is None


def test_fleet_alert_from_summary_ignores_info_signal():
    summary = {
        "top_signal": {
            "id": "fleet:service:svc-a",
            "level": "info",
            "title": "Service signal: svc-a",
            "message": "nominal",
            "latest_run_id": "r1",
            "scope": "service",
        }
    }

    assert fleet_alert_from_summary(summary) is None


def test_fleet_alert_from_summary_maps_warning_signal_to_existing_shape():
    summary = {
        "top_signal": {
            "id": "fleet:service:svc-a",
            "level": "warning",
            "title": "Service signal: svc-a",
            "message": "1 failure across 2 runs",
            "latest_run_id": "r2",
            "scope": "service",
        }
    }

    alert = fleet_alert_from_summary(summary)

    assert alert is not None
    assert alert["level"] == "warning"
    assert alert["source"] == "fleet"
    assert alert["tab"] == "health"
    assert alert["run_id"] == "r2"
    assert alert["signal_id"] == "fleet:service:svc-a"
    assert "Service signal: svc-a" in alert["message"]


def test_merge_alerts_with_fleet_prioritizes_critical_fleet_alert():
    existing = [
        {
            "level": "warning",
            "source": "burnin",
            "message": "Burn-In not passed",
            "tab": "health",
        }
    ]
    summary = {
        "top_signal": {
            "id": "fleet:skill:parse_pdf",
            "level": "critical",
            "title": "Skill signal: parse_pdf",
            "message": "3 failures across 3 runs",
            "latest_run_id": "r3",
            "scope": "skill",
        }
    }

    merged = merge_alerts_with_fleet(existing, summary)

    assert len(merged) == 2
    assert merged[0]["source"] == "fleet"
    assert merged[0]["level"] == "critical"
    assert merged[0]["run_id"] == "r3"
    assert merged[1]["source"] == "burnin"
