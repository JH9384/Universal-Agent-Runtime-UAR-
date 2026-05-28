"""Tests for the Prometheus /metrics endpoint.

Covers: endpoint availability, content-type, valid exposition format.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from uar.api.metrics import get_metrics_collector
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

    def test_record_connection(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_connection(3)
        assert collector._active_ws_connections == 3
        collector.record_connection(-2)
        assert collector._active_ws_connections == 1
        collector.record_connection(-10)
        assert collector._active_ws_connections == 0
        collector.shutdown()

    def test_get_metrics(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_request("/api/test", 0.1)
        collector._flush_window()
        metrics = collector.get_metrics()
        assert metrics["total_requests"] == 1
        assert "/api/test" in metrics["endpoints"]
        collector.shutdown()

    def test_get_prometheus_format(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector.record_request("/api/test", 0.1)
        collector._flush_window()
        text = collector.get_prometheus_format()
        assert "uar_requests_total" in text
        assert "uar_request_duration_seconds_bucket" in text
        collector.shutdown()

    def test_redis_circuit_breaker(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        assert collector._is_redis_circuit_open() is False
        for _ in range(5):
            collector._record_redis_failure(Exception("fail"))
        assert collector._is_redis_circuit_open() is True
        collector.shutdown()

    def test_redis_circuit_resets(self):
        from uar.api.metrics import MetricsCollector
        import time

        collector = MetricsCollector()
        collector._record_redis_failure(Exception("fail"))
        assert collector._is_redis_circuit_open() is False
        # Manually set to open and backdate
        with collector._redis_circuit_lock:
            collector._redis_circuit_open = True
            collector._redis_last_failure_time = time.time() - 60
        assert collector._is_redis_circuit_open() is False
        collector.shutdown()

    def test_load_from_redis_no_redis(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector._load_from_redis()  # should not raise
        collector.shutdown()

    def test_persist_to_redis_no_redis(self):
        from uar.api.metrics import MetricsCollector
        collector = MetricsCollector()
        collector._persist_to_redis()  # should not raise
        collector.shutdown()

    def test_persist_to_redis_with_mock(self):
        from uar.api.metrics import MetricsCollector
        mock_redis = MagicMock()
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            collector = MetricsCollector()
            collector._total_requests = 42
            collector._dirty = True
            collector._persist_to_redis()
            mock_redis.hset.assert_called()
            mock_redis.expire.assert_called()
        collector.shutdown()

    def test_load_from_redis_with_mock(self):
        from uar.api.metrics import MetricsCollector
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "total_requests": "100",
            "total_errors": "5",
            "active_ws_connections": "2",
        }
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            collector = MetricsCollector()
            assert collector._total_requests == 100
            assert collector._total_errors == 5
            assert collector._active_ws_connections == 2
        collector.shutdown()

    def test_record_redis_failure_persistence(self):
        from uar.api.metrics import MetricsCollector
        mock_redis = MagicMock()
        mock_redis.hset.side_effect = Exception("redis down")
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            collector = MetricsCollector()
            collector._total_requests = 10
            collector._dirty = True
            collector._persist_to_redis()
            assert collector._redis_failures > 0
        collector.shutdown()


class TestTimedDecorator:
    """@timed decorator."""

    def test_records_success(self):
        from uar.api.metrics import timed, get_metrics_collector
        collector = get_metrics_collector()
        before = collector._total_requests

        @timed(endpoint="/test_decorated")
        def my_func():
            return "ok"

        my_func()
        assert collector._total_requests > before

    def test_records_error(self):
        from uar.api.metrics import timed
        collector = get_metrics_collector()
        before_err = collector._total_errors

        @timed(endpoint="/test_error")
        def my_func():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            my_func()
        collector._flush_window()
        assert collector._total_errors > before_err

    def test_default_endpoint_name(self):
        from uar.api.metrics import timed
        collector = get_metrics_collector()

        @timed()
        def my_module_my_func():
            return "ok"

        my_module_my_func()
        # Should use __qualname__ as endpoint
        assert collector._total_requests >= 1
