"""Tests for T7 — External Metrics (Prometheus + Grafana).

Covers:
- Prometheus exposition format contains expected metrics
- JSON metrics endpoint shape
- Metrics endpoint auth
- Grafana dashboard JSON validity
"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from uar.api.metrics import MetricsCollector, get_metrics_collector


def _get_client():
    from uar.api.server import app

    return TestClient(app, raise_server_exceptions=True)


@pytest.fixture(autouse=True)
def reset_metrics(monkeypatch):
    """Provide a fresh MetricsCollector for each test."""
    fresh = MetricsCollector()
    fresh._start_time = 0.0  # deterministic uptime
    monkeypatch.setattr(
        "uar.api.metrics._metrics", fresh, raising=False
    )


def test_prometheus_format_has_uptime():
    """Prometheus output includes uptime gauge."""
    collector = get_metrics_collector()
    text = collector.get_prometheus_format()
    assert "# HELP uar_uptime_seconds Process uptime" in text
    assert "# TYPE uar_uptime_seconds gauge" in text
    assert "uar_uptime_seconds" in text


def test_prometheus_format_has_requests():
    """Prometheus output includes request counter."""
    collector = get_metrics_collector()
    collector.record_request("/api/uar/run", 0.1)
    collector._flush_window()
    text = collector.get_prometheus_format()
    assert "uar_requests_total 1" in text
    assert "uar_request_duration_seconds_bucket" in text


def test_prometheus_format_has_errors():
    """Prometheus output includes error counter."""
    collector = get_metrics_collector()
    collector.record_request("/api/uar/run", 0.1, error=True)
    collector._flush_window()
    text = collector.get_prometheus_format()
    assert "uar_errors_total 1" in text
    assert 'uar_request_errors{endpoint="/api/uar/run"} 1' in text


def test_prometheus_format_has_skill_metrics():
    """Prometheus output includes skill histograms."""
    collector = get_metrics_collector()
    collector.record_skill("echo", 0.05)
    collector._flush_window()
    text = collector.get_prometheus_format()
    assert "uar_skill_duration_seconds_bucket" in text
    assert 'skill="echo"' in text


def test_prometheus_format_has_websocket_gauge():
    """Prometheus output includes websocket connection gauge."""
    collector = get_metrics_collector()
    collector.record_connection(3)
    text = collector.get_prometheus_format()
    assert "uar_websocket_connections 3" in text


def test_json_metrics_shape():
    """JSON metrics contain expected top-level keys."""
    collector = get_metrics_collector()
    data = collector.get_metrics()
    assert "uptime_seconds" in data
    assert "total_requests" in data
    assert "total_errors" in data
    assert "endpoints" in data
    assert "skills" in data


def test_metrics_endpoint_returns_prometheus():
    """GET /metrics returns Prometheus text."""
    client = _get_client()
    resp = client.get("/metrics")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/plain")
    assert "uar_requests_total" in resp.text


def test_metrics_json_endpoint():
    """GET /api/metrics/json returns JSON."""
    client = _get_client()
    resp = client.get("/api/metrics/json")
    assert resp.status_code == 200
    data = resp.json()
    assert "total_requests" in data


def test_metrics_endpoint_auth_with_env_key(monkeypatch):
    """METRICS_API_KEY env var gates the metrics endpoint."""
    monkeypatch.setenv("METRICS_API_KEY", "secret-123")
    client = _get_client()
    resp = client.get("/metrics")
    assert resp.status_code == 401
    resp = client.get(
        "/metrics",
        headers={"Authorization": "Bearer secret-123"},
    )
    assert resp.status_code == 200


def test_grafana_dashboard_json_is_valid():
    """Operational dashboard JSON parses and has required fields."""
    import pathlib

    path = (
        pathlib.Path(__file__).parent.parent.parent
        / "deploy/grafana/dashboards/uar-operational.json"
    )
    raw = path.read_text()
    dashboard = json.loads(raw)
    assert dashboard["dashboard"]["title"] == "UAR Operational Metrics"
    panels = dashboard["dashboard"]["panels"]
    titles = {p["title"] for p in panels}
    assert "Uptime" in titles
    assert "Total Requests" in titles
    assert "Total Errors" in titles
    assert "Request Rate" in titles
    assert "Error Rate" in titles
    assert "Request Duration p50" in titles
    assert "Request Duration p99" in titles
    assert "Skill Execution Count" in titles
    assert "Skill Errors" in titles
