"""
Metrics middleware and collection for UAR API.
Provides Prometheus-compatible metrics and basic runtime statistics.
"""

import time
import threading
from collections import defaultdict
from typing import Dict, Any
from dataclasses import dataclass


@dataclass
class RequestMetrics:
    count: int = 0
    total_duration: float = 0.0
    errors: int = 0


class MetricsCollector:
    """Collects and aggregates request metrics."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._endpoint_metrics: Dict[str, RequestMetrics] = defaultdict(
            RequestMetrics
        )
        self._total_requests = 0
        self._total_errors = 0
        self._start_time = time.time()

    def record_request(
        self, endpoint: str, duration: float, error: bool = False
    ) -> None:
        """Record a request metric."""
        with self._lock:
            self._total_requests += 1
            metrics = self._endpoint_metrics[endpoint]
            metrics.count += 1
            metrics.total_duration += duration
            if error:
                metrics.errors += 1
                self._total_errors += 1

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
                    "error_rate": round(m.errors / m.count * 100, 2)
                    if m.count > 0
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
                "# HELP uar_request_duration_seconds Request duration"
            )
            lines.append("# TYPE uar_request_duration_seconds histogram")

            for endpoint, m in self._endpoint_metrics.items():
                avg = m.total_duration / m.count if m.count > 0 else 0.0
                lines.append(
                    f'uar_request_duration_seconds{{endpoint="{endpoint}"}} '
                    f'{avg:.4f}'
                )
                lines.append(
                    f'uar_request_count{{endpoint="{endpoint}"}} {m.count}'
                )
                lines.append(
                    f'uar_request_errors{{endpoint="{endpoint}"}} {m.errors}'
                )

            return "\n".join(lines) + "\n"


# Global metrics instance
_metrics = MetricsCollector()


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    return _metrics
