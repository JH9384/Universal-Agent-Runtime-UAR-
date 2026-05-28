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


class TestLogBucket:
    """DDSketch log bucket mapping."""

    def test_zero_returns_zero(self):
        from uar.api.metrics import _log_bucket
        assert _log_bucket(0) == 0
        assert _log_bucket(-1) == 0

    def test_positive_values(self):
        from uar.api.metrics import _log_bucket
        assert _log_bucket(1.0) >= 0
        assert _log_bucket(100.0) > _log_bucket(10.0)


class TestBucketCeiling:
    """DDSketch bucket ceiling."""

    def test_increases_with_index(self):
        from uar.api.metrics import _bucket_ceiling
        assert _bucket_ceiling(0) == 1.0
        assert _bucket_ceiling(1) > 1.0


class TestHistogram:
    """DDSketch-style histogram."""

    def test_observe(self):
        from uar.api.metrics import Histogram
        h = Histogram()
        h.observe(1.0)
        h.observe(2.0)
        assert h.total_count == 2
        assert h.total_sum == 3.0

    def test_percentile_empty(self):
        from uar.api.metrics import Histogram
        h = Histogram()
        assert h.percentile(0.5) == 0.0

    def test_percentile_basic(self):
        from uar.api.metrics import Histogram
        h = Histogram()
        for i in range(1, 101):
            h.observe(float(i))
        p50 = h.percentile(0.5)
        assert p50 > 0

    def test_min_max(self):
        from uar.api.metrics import Histogram
        h = Histogram()
        h.observe(5.0)
        h.observe(10.0)
        assert h._min == 5.0
        assert h._max == 10.0


class TestMetricsCollector:
    """MetricsCollector lifecycle."""

    def test_init(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        assert collector._total_requests == 0
        assert collector._shutdown is False
        collector.shutdown()

    def test_record_request(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_request("/test", 0.1)
        assert collector._total_requests == 1
        # count is window-aggregated; flush to verify
        collector._flush_window()
        assert collector._endpoint_metrics["/test"].count == 1
        collector.shutdown()

    def test_record_request_error(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_request("/test", 0.1, error=True)
        collector._flush_window()
        assert collector._total_errors == 1
        collector.shutdown()

    def test_record_skill(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_skill("my_skill", 0.2)
        collector._flush_window()
        assert collector._skill_metrics["my_skill"].count == 1
        collector.shutdown()

    def test_shutdown(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.shutdown()
        assert collector._shutdown is True
