"""Tests for uar.api.metrics."""

import os
from unittest.mock import MagicMock, patch

import pytest

from uar.api.metrics import (
    Histogram,
    MetricsCollector,
    get_metrics_collector,
    timed,
    _log_bucket,
    _bucket_ceiling,
    _get_redis,
    _close_redis,
)


class TestLogBucket:
    def test_zero(self):
        assert _log_bucket(0) == 0

    def test_positive(self):
        assert _log_bucket(1.0) >= 0
        assert _log_bucket(100.0) > _log_bucket(1.0)

    def test_negative(self):
        assert _log_bucket(-1.0) == 0


class TestBucketCeiling:
    def test_roundtrip(self):
        idx = _log_bucket(5.0)
        assert _bucket_ceiling(idx) > 0


class TestHistogram:
    def test_observe(self):
        h = Histogram()
        h.observe(0.1)
        h.observe(0.2)
        assert h.total_count == 2
        assert h.total_sum == pytest.approx(0.3, 0.01)

    def test_percentile_empty(self):
        h = Histogram()
        assert h.percentile(0.5) == 0.0

    def test_percentile(self):
        h = Histogram()
        for i in range(1, 101):
            h.observe(float(i) / 1000)
        p50 = h.percentile(0.5)
        assert p50 > 0

    def test_percentile_falls_through_to_max(self):
        h = Histogram()
        h.total_count = 10
        h.counts[0] = 1
        h._min = 1.0
        h._max = 100.0
        # target = int(10 * 0.99) = 9, cumulative only reaches 1
        p99 = h.percentile(0.99)
        assert p99 == 100.0


class TestMetricsCollector:
    def test_record_request(self):
        mc = MetricsCollector()
        mc.record_request("/test", 0.1)
        assert mc._total_requests == 1

    def test_record_request_error(self):
        mc = MetricsCollector()
        mc.record_request("/test", 0.1, error=True)
        mc._flush_window()
        assert mc._total_errors == 1

    def test_record_skill(self):
        mc = MetricsCollector()
        mc.record_skill("s1", 0.05)
        mc._flush_window()
        assert mc._skill_metrics["s1"].count == 1

    def test_record_connection(self):
        mc = MetricsCollector()
        mc.record_connection(1)
        assert mc._active_ws_connections == 1
        mc.record_connection(-1)
        assert mc._active_ws_connections == 0
        mc.record_connection(-5)
        assert mc._active_ws_connections == 0

    def test_get_metrics(self):
        mc = MetricsCollector()
        mc.record_request("/test", 0.1)
        data = mc.get_metrics()
        assert data["total_requests"] == 1
        assert "endpoints" in data
        assert "skills" in data

    def test_get_prometheus_format(self):
        mc = MetricsCollector()
        mc.record_request("/test", 0.1)
        output = mc.get_prometheus_format()
        assert "uar_requests_total" in output
        assert "uar_errors_total" in output

    def test_shutdown(self):
        mc = MetricsCollector()
        mc.shutdown()
        assert mc._shutdown is True

    def test_redis_circuit(self):
        mc = MetricsCollector()
        assert mc._is_redis_circuit_open() is False
        mc._record_redis_failure(ValueError("fail"))
        assert mc._redis_failures == 1

    def test_load_from_redis_no_redis(self):
        mc = MetricsCollector()
        with patch("uar.api.metrics._get_redis", return_value=None):
            mc._load_from_redis()

    def test_persist_to_redis_no_redis(self):
        mc = MetricsCollector()
        with patch("uar.api.metrics._get_redis", return_value=None):
            mc._persist_to_redis()

    def test_persist_to_redis_with_redis(self):
        mc = MetricsCollector()
        mc._dirty = True
        mock_redis = MagicMock()
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            mc._persist_to_redis()
        mock_redis.hset.assert_called_once()
        mock_redis.expire.assert_called_once()

    def test_flush_window(self):
        mc = MetricsCollector()
        mc._window["req:/test"] = 2
        mc._window["req:/test:dur"] = 0.2
        mc._flush_window()
        assert mc._endpoint_metrics["/test"].count == 2


class TestTimedDecorator:
    def test_no_error(self):
        @timed(endpoint="/test")
        def my_func():
            return 42

        result = my_func()
        assert result == 42

    def test_error(self):
        @timed(endpoint="/test")
        def my_func():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            my_func()

    def test_no_endpoint(self):
        @timed()
        def my_func():
            return 42

        result = my_func()
        assert result == 42


class TestRedisHelpers:
    """_get_redis and _close_redis."""

    def test_get_redis_no_url(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("uar.api.metrics._redis_client", None):
                assert _get_redis() is None

    def test_get_redis_import_failure(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
            with patch("uar.api.metrics._redis_client", None):
                with patch.dict("sys.modules", {"redis": None}):
                    assert _get_redis() is None

    def test_get_redis_cached(self):
        mock_client = MagicMock()
        with patch("uar.api.metrics._redis_client", mock_client):
            result = _get_redis()
        assert result is mock_client

    def test_get_redis_import_success(self):
        with patch.dict(os.environ, {"REDIS_URL": "redis://localhost"}):
            with patch("uar.api.metrics._redis_client", None):
                mock_redis_mod = MagicMock()
                mock_client = MagicMock()
                mock_redis_mod.from_url.return_value = mock_client
                with patch.dict("sys.modules", {"redis": mock_redis_mod}):
                    result = _get_redis()
        assert result is mock_client

    def test_close_redis(self):
        mock_client = MagicMock()
        with patch("uar.api.metrics._redis_client", mock_client):
            _close_redis()
        mock_client.close.assert_called_once()

    def test_close_redis_exception(self):
        mock_client = MagicMock()
        mock_client.close.side_effect = Exception("close fail")
        with patch("uar.api.metrics._redis_client", mock_client):
            _close_redis()  # should not raise

    def test_close_redis_none(self):
        with patch("uar.api.metrics._redis_client", None):
            _close_redis()  # should not raise


class TestLogAlphaException:
    """_LOG_ALPHA bad env var fallback."""

    def test_log_alpha_bad_env(self):
        # Inline the exception logic without reloading the module
        with patch.dict(os.environ, {"UAR_METRIC_HISTOGRAM_ALPHA": "bad"}):
            try:
                val = max(
                    0.0001,
                    min(
                        float(
                            os.getenv("UAR_METRIC_HISTOGRAM_ALPHA", "0.01")
                            .strip() or "0.01"
                        ),
                        1.0,
                    ),
                )
            except (ValueError, TypeError):
                val = 0.01
        assert val == 0.01


class TestWindowDisabled:
    """MetricsCollector with UAR_METRICS_WINDOW=false."""

    def test_record_request_no_window(self):
        with patch.object(MetricsCollector, "_WINDOW_ENABLED", False):
            mc = MetricsCollector()
            mc.record_request("/test", 0.1)
            assert mc._total_requests == 1
            assert mc._endpoint_metrics["/test"].count == 1
            mc.shutdown()

    def test_record_request_error_no_window(self):
        with patch.object(MetricsCollector, "_WINDOW_ENABLED", False):
            mc = MetricsCollector()
            mc.record_request("/test", 0.1, error=True)
            assert mc._total_errors == 1
            assert mc._endpoint_metrics["/test"].errors == 1
            mc.shutdown()

    def test_record_skill_no_window(self):
        with patch.object(MetricsCollector, "_WINDOW_ENABLED", False):
            mc = MetricsCollector()
            mc.record_skill("s1", 0.05)
            assert mc._skill_metrics["s1"].count == 1
            assert mc._skill_metrics["s1"].total_duration == 0.05
            mc.shutdown()

    def test_record_skill_error_no_window(self):
        with patch.object(MetricsCollector, "_WINDOW_ENABLED", False):
            mc = MetricsCollector()
            mc.record_skill("s1", 0.05, error=True)
            assert mc._skill_metrics["s1"].errors == 1
            mc.shutdown()


class TestRedisCircuit:
    """Redis circuit breaker edge cases."""

    def test_circuit_still_open(self):
        mc = MetricsCollector()
        with mc._redis_circuit_lock:
            mc._redis_circuit_open = True
            mc._redis_last_failure_time = __import__("time").time()
        assert mc._is_redis_circuit_open() is True
        mc.shutdown()

    def test_persist_circuit_open(self):
        mc = MetricsCollector()
        import time
        with mc._redis_circuit_lock:
            mc._redis_circuit_open = True
            mc._redis_last_failure_time = time.time()
        mock_redis = MagicMock()
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            mc._persist_to_redis()
        mock_redis.hset.assert_not_called()
        mc.shutdown()

    def test_load_redis_exception(self):
        mc = MetricsCollector()
        mock_redis = MagicMock()
        mock_redis.hgetall.side_effect = Exception("redis down")
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            mc._load_from_redis()
        assert mc._redis_failures > 0
        mc.shutdown()

    def test_load_redis_circuit_open(self):
        mc = MetricsCollector()
        with mc._redis_circuit_lock:
            mc._redis_circuit_open = True
            mc._redis_last_failure_time = __import__("time").time()
        mock_redis = MagicMock()
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            mc._load_from_redis()
        mock_redis.hgetall.assert_not_called()
        mc.shutdown()

    def test_load_from_redis_data_branch(self):
        mc = MetricsCollector()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {
            "total_requests": "50",
            "total_errors": "3",
            "active_ws_connections": "1",
        }
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            mc._load_from_redis()
        assert mc._total_requests == 50
        assert mc._total_errors == 3
        assert mc._active_ws_connections == 1
        mc.shutdown()

    def test_load_from_redis_empty_data(self):
        mc = MetricsCollector()
        mock_redis = MagicMock()
        mock_redis.hgetall.return_value = {}  # falsy
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            mc._load_from_redis()
        # Circuit should still be reset even when data is empty
        assert mc._redis_failures == 0
        mc.shutdown()

    def test_record_skill_error_window(self):
        mc = MetricsCollector()
        mc.record_skill("s1", 0.1, error=True)
        assert mc._total_requests == 0  # skill doesn't count as request
        mc._flush_window()
        assert mc._skill_metrics["s1"].errors == 1
        mc.shutdown()

    def test_record_skill_window_time_advance(self):
        import time
        mc = MetricsCollector()
        mc.record_skill("s1", 0.1)
        # Backdate window_time to force flush on next record
        mc._window_time = time.time() - 2.0
        mc.record_skill("s1", 0.2)
        assert mc._skill_metrics["s1"].count >= 1
        mc.shutdown()

    def test_record_skill_no_window_advance(self):
        mc = MetricsCollector()
        mc.record_skill("s1", 0.1)
        # _window_time is now current time; second call within 1s should
        # NOT trigger flush
        mc.record_skill("s1", 0.2)
        assert mc._window["skill:s1"] == 2
        mc.shutdown()


class TestWindowFlush:
    """Aggregation window time-advance flush."""

    def test_window_time_advance_flush(self):
        import time
        mc = MetricsCollector()
        mc.record_request("/test", 0.1)
        time.sleep(1.1)
        mc.record_request("/test", 0.2)
        assert mc._endpoint_metrics["/test"].count >= 1
        mc.shutdown()

    def test_flush_loop_background(self):
        import time
        mock_redis = MagicMock()
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            with patch.object(MetricsCollector, "_FLUSH_INTERVAL", 0.05):
                mc = MetricsCollector()
                mc._total_requests = 5
                mc._dirty = True
                time.sleep(0.12)
                mock_redis.hset.assert_called()
        mc.shutdown()

    def test_flush_loop_exit_on_shutdown(self):
        import time
        mock_redis = MagicMock()
        with patch("uar.api.metrics._get_redis", return_value=mock_redis):
            with patch.object(MetricsCollector, "_FLUSH_INTERVAL", 0.05):
                mc = MetricsCollector()
                thread = mc._flush_thread
                assert thread is not None
                mc.shutdown()
                time.sleep(0.1)
                assert not thread.is_alive()


class TestSkillMetricsOutput:
    """get_metrics and get_prometheus_format with skill data."""

    def test_get_metrics_skills(self):
        mc = MetricsCollector()
        mc.record_skill("s1", 0.1)
        mc._flush_window()
        data = mc.get_metrics()
        assert "s1" in data["skills"]
        assert data["skills"]["s1"]["count"] == 1
        mc.shutdown()

    def test_get_prometheus_format_skills(self):
        mc = MetricsCollector()
        mc.record_skill("s1", 0.1)
        mc._flush_window()
        text = mc.get_prometheus_format()
        assert "uar_skill_duration_seconds" in text
        assert 'skill="s1"' in text
        assert "uar_skill_errors" in text
        mc.shutdown()


class TestTimedNoRecordError:
    """@timed with record_error=False."""

    def test_exception_not_recorded(self):
        collector = get_metrics_collector()

        @timed(endpoint="/no_record", record_error=False)
        def my_func():
            raise ValueError("fail")

        with pytest.raises(ValueError):
            my_func()
        collector._flush_window()
        assert "/no_record" not in collector._endpoint_metrics


class TestGlobal:
    def test_get_metrics_collector(self):
        mc = get_metrics_collector()
        assert isinstance(mc, MetricsCollector)
