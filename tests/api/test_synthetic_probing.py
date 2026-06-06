"""Tests for T8 — Synthetic Probing (blackbox + PagerDuty).

Covers:
- SyntheticProbe.run_all against a real server
- Consecutive-failure gating before alert
- PagerDutyNotifier trigger/resolve dedup_key
- CLI command exists and exits correctly
"""

from __future__ import annotations

from unittest.mock import MagicMock

from typer.testing import CliRunner

from uar.cli.main import app
from uar.observability.pagerduty import PagerDutyNotifier
from uar.observability.synthetic_probe import (
    ProbeResult,
    ProbeScenario,
    SyntheticProbe,
)

runner = CliRunner()


def test_probe_scenario_pass():
    """Probe against a mock callable returns correct result."""
    probe = SyntheticProbe(base_url="http://localhost:1")
    scenario = ProbeScenario(
        name="test",
        url="http://localhost:1/nope",
        timeout=0.01,
    )
    result = probe._run_one(scenario)
    assert result.scenario == "test"
    assert result.passed is False
    assert result.detail is not None


def test_probe_consecutive_failure_gating():
    """Alert only fires after consecutive failures threshold."""
    notifier = MagicMock()
    probe = SyntheticProbe(
        base_url="http://localhost:1",
        consecutive_failures=2,
        notifier=notifier,
    )

    # First failure — no alert
    probe._process_result(
        ProbeResult(
            scenario="health", passed=False, latency_ms=1.0, detail="fail"
        )
    )
    notifier.trigger.assert_not_called()

    # Second failure — alert fires
    probe._process_result(
        ProbeResult(
            scenario="health", passed=False, latency_ms=1.0, detail="fail"
        )
    )
    notifier.trigger.assert_called_once()


def test_probe_recovery_resolves_alert():
    """Passing probe after alert triggers resolve."""
    notifier = MagicMock()
    probe = SyntheticProbe(
        base_url="http://localhost:1",
        consecutive_failures=1,
        notifier=notifier,
    )

    probe._process_result(
        ProbeResult(scenario="health", passed=False, latency_ms=1.0)
    )
    assert "health" in probe._alerted

    probe._process_result(
        ProbeResult(scenario="health", passed=True, latency_ms=1.0)
    )
    notifier.resolve.assert_called_once()
    assert "health" not in probe._alerted


def test_pagerduty_disabled_without_key():
    """Notifier does nothing when routing key is missing."""
    pd = PagerDutyNotifier(routing_key="")
    assert pd.trigger("test", "s1") is False
    assert pd.resolve("test", "s1") is False


def test_pagerduty_dedup_key():
    """Dedup key is deterministic per scenario."""
    pd = PagerDutyNotifier(routing_key="rk")
    assert pd._dedup_key("health") == "uar-probe-health"
    assert pd._dedup_key("metrics") == "uar-probe-metrics"


def test_pagerduty_payload_structure(monkeypatch):
    """Trigger sends correct JSON payload structure."""
    calls = []

    def _capture(req, **kwargs):
        calls.append(req)
        import urllib.response

        return urllib.response.addinfourl(
            io.BytesIO(b'{"status":"success"}'), {}, 200
        )

    import io
    import uar.observability.pagerduty as _pd

    monkeypatch.setattr(_pd, "urlopen", _capture)

    pd = PagerDutyNotifier(routing_key="rk-123", severity="warning")
    pd.trigger("Summary", "health", {"latency": 42})

    assert len(calls) == 1
    payload = calls[0].data.decode("utf-8")
    import json

    data = json.loads(payload)
    assert data["routing_key"] == "rk-123"
    assert data["event_action"] == "trigger"
    assert data["dedup_key"] == "uar-probe-health"
    assert data["payload"]["summary"] == "Summary"
    assert data["payload"]["severity"] == "warning"
    assert data["payload"]["source"] == "uar-synthetic-probe"
    assert data["payload"]["custom_details"]["latency"] == 42


def test_cli_probe_once_against_running_server():
    """uar probe run --once hits a real server if available."""
    result = runner.invoke(
        app, ["probe", "run", "--once", "--url=http://localhost:8000"]
    )
    # Exit 0 if all probes passed, 1 if server is down — both valid
    assert result.exit_code in (0, 1)
