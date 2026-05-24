"""
Metrics middleware and collection for UAR API.
Provides Prometheus-compatible metrics and basic runtime statistics.
"""

import math
import os
import time
import threading
import functools
from collections import defaultdict
from typing import Dict, Any, Callable, Optional
from dataclasses import dataclass, field

# Optional Redis persistence for cross-process metrics
_redis_client: Any = None  # type: ignore[name-defined]


def _get_redis():
    """Lazy Redis connection for metrics persistence."""
    global _redis_client
    if _redis_client is not None:
        return _redis_client
    redis_url = os.getenv("REDIS_URL", "").strip()
    if not redis_url:
        return None
    try:
        import redis

        _redis_client = redis.from_url(redis_url, decode_responses=True)
        return _redis_client
    except Exception:  # noqa: BLE001
        return None


# DDSketch-style histogram: logarithmic buckets for sub-linear memory growth.
# Relative accuracy ~1% by default (alpha=0.01).
_LOG_ALPHA = float(os.getenv("UAR_METRIC_HISTOGRAM_ALPHA", "0.01"))


def _log_bucket(value: float, alpha: float = _LOG_ALPHA) -> int:
    """Map a positive value to a DDSketch-style log bucket index."""
    if value <= 0:
        return 0
    gamma = (1 + alpha) / (1 - alpha)
    return int(round(math.log(value, gamma)))


def _bucket_ceiling(index: int, alpha: float = _LOG_ALPHA) -> float:
    """Upper bound of the DDSketch bucket at *index*."""
    gamma = (1 + alpha) / (1 - alpha)
    return gamma ** index


@dataclass
class Histogram:
    """DDSketch-style histogram with logarithmic buckets.

    Memory grows sub-linearly with the number of observations
    (~O(log(max_value))) instead of O(n) for exact storage.
    """
    alpha: float = field(default=_LOG_ALPHA)
    counts: Dict[int, int] = field(
        default_factory=lambda: defaultdict(int)
    )
    total_sum: float = 0.0
    total_count: int = 0
    _min: float = float("inf")
    _max: float = 0.0

    def observe(self, value: float) -> None:
        self.total_sum += value
        self.total_count += 1
        if value < self._min:
            self._min = value
        if value > self._max:
            self._max = value
        idx = _log_bucket(value, self.alpha)
        self.counts[idx] += 1

    def percentile(self, p: float) -> float:
        """Return approximate percentile from DDSketch histogram."""
        if self.total_count == 0:
            return 0.0
        target = int(self.total_count * p)
        if target == 0:
            return self._min
        cumulative = 0
        for idx in sorted(self.counts):
            cumulative += self.counts[idx]
            if cumulative >= target:
                return _bucket_ceiling(idx, self.alpha)
        return self._max


@dataclass
class RequestMetrics:
    count: int = 0
    total_duration: float = 0.0
    errors: int = 0
    histogram: Histogram = field(default_factory=Histogram)


@dataclass
class SkillMetrics:
    count: int = 0
    total_duration: float = 0.0
    errors: int = 0
    histogram: Histogram = field(default_factory=Histogram)


class MetricsCollector:
    """Collects and aggregates request and skill metrics."""

    _REDIS_KEY = "uar:metrics:totals"
    _FLUSH_INTERVAL = float(os.getenv("UAR_METRICS_FLUSH_SEC", "5.0"))

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._endpoint_metrics: Dict[str, RequestMetrics] = defaultdict(
            RequestMetrics
        )
        self._skill_metrics: Dict[str, SkillMetrics] = defaultdict(
            SkillMetrics
        )
        self._total_requests = 0
        self._total_errors = 0
        self._active_ws_connections = 0
        self._start_time = time.time()
        self._dirty = False
        self._flush_thread: Optional[threading.Thread] = None
        self._shutdown = False
        self._load_from_redis()
        self._start_flush_thread()

    def _start_flush_thread(self) -> None:
        """Start background thread that flushes metrics to Redis."""
        if _get_redis() is None:
            return
        self._flush_thread = threading.Thread(
            target=self._flush_loop, daemon=True
        )
        self._flush_thread.start()

    def _flush_loop(self) -> None:
        """Periodic flush of dirty metrics to Redis."""
        while not self._shutdown:
            time.sleep(self._FLUSH_INTERVAL)
            if self._dirty:
                self._persist_to_redis()

    def shutdown(self) -> None:
        """Signal flush thread to stop and do final persist."""
        self._shutdown = True
        if self._dirty:
            self._persist_to_redis()

    def record_request(
        self, endpoint: str, duration: float, error: bool = False
    ) -> None:
        """Record a request metric."""
        with self._lock:
            self._total_requests += 1
            metrics = self._endpoint_metrics[endpoint]
            metrics.count += 1
            metrics.total_duration += duration
            metrics.histogram.observe(duration)
            if error:
                metrics.errors += 1
                self._total_errors += 1
            self._dirty = True

    def record_skill(
        self, skill_name: str, duration: float, error: bool = False
    ) -> None:
        """Record a skill execution metric."""
        with self._lock:
            metrics = self._skill_metrics[skill_name]
            metrics.count += 1
            metrics.total_duration += duration
            metrics.histogram.observe(duration)
            if error:
                metrics.errors += 1
            self._dirty = True

    def record_connection(self, delta: int = 1) -> None:
        """Adjust the active WebSocket connection gauge."""
        with self._lock:
            self._active_ws_connections = max(
                0, self._active_ws_connections + delta
            )
            self._dirty = True

    def _load_from_redis(self) -> None:
        """Hydrate simple counters from Redis on startup."""
        r = _get_redis()
        if r is None:
            return
        try:
            data = r.hgetall(self._REDIS_KEY)
            if data:
                self._total_requests = int(data.get("total_requests", 0))
                self._total_errors = int(data.get("total_errors", 0))
                self._active_ws_connections = int(
                    data.get("active_ws_connections", 0)
                )
        except Exception:  # noqa: BLE001
            pass

    def _persist_to_redis(self) -> None:
        """Write simple counters to Redis for cross-process recovery."""
        r = _get_redis()
        if r is None:
            return
        try:
            with self._lock:
                r.hset(
                    self._REDIS_KEY,
                    mapping={
                        "total_requests": self._total_requests,
                        "total_errors": self._total_errors,
                        "active_ws_connections": self._active_ws_connections,
                    },
                )
                self._dirty = False
            r.expire(self._REDIS_KEY, 86400)  # 24 h TTL
        except Exception:  # noqa: BLE001
            pass

    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics snapshot."""
        with self._lock:
            uptime = time.time() - self._start_time
            endpoint_stats = {}
            for endpoint, m in self._endpoint_metrics.items():
                avg_duration = (
                    m.total_duration / m.count if m.count > 0 else 0.0
                )
                endpoint_stats[endpoint] = {
                    "count": m.count,
                    "avg_duration_ms": round(avg_duration * 1000, 2),
                    "p50_ms": round(m.histogram.percentile(0.50) * 1000, 2),
                    "p99_ms": round(m.histogram.percentile(0.99) * 1000, 2),
                    "error_rate": round(m.errors / m.count * 100, 2)
                    if m.count > 0
                    else 0.0,
                }
            skill_stats = {}
            for skill, sm in self._skill_metrics.items():
                avg_duration = (
                    sm.total_duration / sm.count if sm.count > 0 else 0.0
                )
                skill_stats[skill] = {
                    "count": sm.count,
                    "avg_duration_ms": round(avg_duration * 1000, 2),
                    "p50_ms": round(sm.histogram.percentile(0.50) * 1000, 2),
                    "p99_ms": round(sm.histogram.percentile(0.99) * 1000, 2),
                    "error_rate": round(sm.errors / sm.count * 100, 2)
                    if sm.count > 0
                    else 0.0,
                }
            return {
                "uptime_seconds": round(uptime, 2),
                "total_requests": self._total_requests,
                "total_errors": self._total_errors,
                "error_rate_percent": round(
                    self._total_errors / self._total_requests * 100, 2
                )
                if self._total_requests > 0
                else 0.0,
                "endpoints": endpoint_stats,
                "skills": skill_stats,
            }

    def get_prometheus_format(self) -> str:
        """Export metrics in Prometheus exposition format."""
        with self._lock:
            lines = []
            lines.append("# HELP uar_requests_total Total requests")
            lines.append("# TYPE uar_requests_total counter")
            lines.append(f"uar_requests_total {self._total_requests}")

            lines.append("# HELP uar_errors_total Total errors")
            lines.append("# TYPE uar_errors_total counter")
            lines.append(f"uar_errors_total {self._total_errors}")

            lines.append(
                "# HELP uar_websocket_connections Active WebSocket "
                "connections"
            )
            lines.append("# TYPE uar_websocket_connections gauge")
            lines.append(
                f"uar_websocket_connections "
                f"{self._active_ws_connections}"
            )

            # Request duration histogram (DDSketch buckets)
            lines.append(
                "# HELP uar_request_duration_seconds Request duration"
            )
            lines.append("# TYPE uar_request_duration_seconds histogram")
            for endpoint, m in self._endpoint_metrics.items():
                cumulative = 0
                for idx in sorted(m.histogram.counts):
                    cumulative += m.histogram.counts[idx]
                    le = f"{_bucket_ceiling(idx, m.histogram.alpha):.6f}"
                    lines.append(
                        f'uar_request_duration_seconds_bucket'
                        f'{{endpoint="{endpoint}",le="{le}"}} {cumulative}'
                    )
                lines.append(
                    f'uar_request_duration_seconds_bucket'
                    f'{{endpoint="{endpoint}",le="+Inf"}} {m.count}'
                )
                lines.append(
                    f'uar_request_duration_seconds_count'
                    f'{{endpoint="{endpoint}"}} {m.count}'
                )
                lines.append(
                    f'uar_request_duration_seconds_sum'
                    f'{{endpoint="{endpoint}"}} '
                    f"{m.histogram.total_sum:.4f}"
                )
                lines.append(
                    f'uar_request_errors'
                    f'{{endpoint="{endpoint}"}} {m.errors}'
                )

            # Skill duration histogram (DDSketch buckets)
            lines.append(
                "# HELP uar_skill_duration_seconds Skill execution duration"
            )
            lines.append("# TYPE uar_skill_duration_seconds histogram")
            for skill, sm in self._skill_metrics.items():
                cumulative = 0
                for idx in sorted(sm.histogram.counts):
                    cumulative += sm.histogram.counts[idx]
                    le = f"{_bucket_ceiling(idx, sm.histogram.alpha):.6f}"
                    lines.append(
                        f'uar_skill_duration_seconds_bucket'
                        f'{{skill="{skill}",le="{le}"}} {cumulative}'
                    )
                lines.append(
                    f'uar_skill_duration_seconds_bucket'
                    f'{{skill="{skill}",le="+Inf"}} {sm.count}'
                )
                lines.append(
                    f'uar_skill_duration_seconds_count'
                    f'{{skill="{skill}"}} {sm.count}'
                )
                lines.append(
                    f'uar_skill_duration_seconds_sum'
                    f'{{skill="{skill}"}} '
                    f"{sm.histogram.total_sum:.4f}"
                )
                lines.append(
                    f'uar_skill_errors'
                    f'{{skill="{skill}"}} {sm.errors}'
                )

            return "\n".join(lines) + "\n"


# Global metrics instance
_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics


def timed(
    endpoint: Optional[str] = None,
    record_error: bool = True,
) -> Callable:
    """Decorator to auto-time a function and record metrics.

    Usage::
        @timed(endpoint="/api/uar/run")
        async def run_goal(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        name = endpoint or func.__qualname__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            collector = get_metrics_collector()
            start = time.perf_counter()
            error = False
            try:
                return func(*args, **kwargs)
            except Exception:
                error = True
                if record_error:
                    duration = time.perf_counter() - start
                    collector.record_request(name, duration, error=True)
                raise
            finally:
                if not error:
                    duration = time.perf_counter() - start
                    collector.record_request(name, duration, error=False)
        return wrapper
    return decorator
