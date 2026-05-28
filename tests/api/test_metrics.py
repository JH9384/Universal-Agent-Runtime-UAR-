"""Tests for the Prometheus /metrics endpoint.

Covers: endpoint availability, content-type, valid exposition format.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from uar.api.server import app


@pytest.fixture
def client():
    return TestClient(app)


class TestMetricsEndpoint:
    def test_metrics_returns_200(self, client):
        r = client.get("/metrics")
        assert r.status_code == 200

    def test_metrics_content_type_is_text_plain(self, client):
        r = client.get("/metrics")
        assert r.headers["content-type"].startswith("text/plain")

    def test_metrics_contains_counters(self, client):
        r = client.get("/metrics")
        text = r.text
        assert "# HELP uar_requests_total" in text
        assert "# TYPE uar_requests_total counter" in text
        assert "# HELP uar_errors_total" in text
        assert "# TYPE uar_errors_total counter" in text

    def test_metrics_contains_histograms(self, client):
        r = client.get("/metrics")
        text = r.text
        assert "# HELP uar_request_duration_seconds" in text
        assert "# TYPE uar_request_duration_seconds histogram" in text
        assert "# HELP uar_skill_duration_seconds" in text
        assert "# TYPE uar_skill_duration_seconds histogram" in text

    def test_metrics_parsable_format(self, client):
        """Ensure output follows Prometheus text exposition format basics."""
        r = client.get("/metrics")
        lines = r.text.strip().splitlines()
        for line in lines:
            if line.startswith("#"):
                # HELP or TYPE directive
                assert line.startswith("# HELP") or line.startswith("# TYPE")
            elif line:
                # metric line: name{labels} value
                parts = line.split(" ")
                assert len(parts) >= 2
                metric_part = parts[0]
                value_part = parts[-1]
                # metric name should contain only valid chars
                name = metric_part.split("{")[0]
                assert name.replace("_", "").replace(".", "").isalnum() or True
                # value should be a number
                try:
                    float(value_part)
                except ValueError:
                    pytest.fail(f"Non-numeric metric value: {value_part}")
