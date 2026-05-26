"""UOR Alignment Metrics - Prometheus metrics for upstream drift detection.

Provides metrics for tracking UOR-Framework alignment status,
drift detection, and validation health.
"""
from __future__ import annotations

import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)


class UORAlignmentMetrics:
    """Metrics collector for UOR alignment status."""

    def __init__(self):
        self._last_check_time: Optional[float] = None
        self._upstream_version: Optional[str] = None
        self._local_version: Optional[str] = None
        self._validation_status: str = "unknown"
        self._drift_detected: bool = False
        self._artifacts_fresh: bool = False

    def record_alignment_check(
        self,
        local_version: str,
        upstream_version: str,
        validation_passed: bool,
    ) -> None:
        """Record an alignment check result."""
        self._last_check_time = time.time()
        self._local_version = local_version
        self._upstream_version = upstream_version
        self._artifacts_fresh = validation_passed
        self._drift_detected = local_version != upstream_version
        self._validation_status = "valid" if validation_passed else "invalid"

        if self._drift_detected:
            logger.warning(
                f"UOR alignment drift detected: "
                f"local={local_version}, upstream={upstream_version}"
            )

    def record_validation_failure(self, error: str) -> None:
        """Record a validation failure."""
        self._validation_status = f"error: {error}"
        logger.error(f"UOR validation failed: {error}")

    def get_prometheus_metrics(self) -> str:
        """Export UOR alignment metrics in Prometheus format."""
        lines = []

        # Alignment drift gauge (1 if drift detected, 0 if aligned)
        drift_value = 1 if self._drift_detected else 0
        lines.append("# HELP uor_alignment_drift UOR alignment drift detected")
        lines.append("# TYPE uor_alignment_drift gauge")
        lines.append(f"uor_alignment_drift {drift_value}")

        # Artifacts fresh gauge (1 if validation passed, 0 otherwise)
        fresh_value = 1 if self._artifacts_fresh else 0
        lines.append("# HELP uor_artifacts_fresh Pinned artifacts valid")
        lines.append("# TYPE uor_artifacts_fresh gauge")
        lines.append(f"uor_artifacts_fresh {fresh_value}")

        # Last check timestamp
        if self._last_check_time:
            lines.append("# HELP uor_alignment_last_check Last check time")
            lines.append("# TYPE uor_alignment_last_check gauge")
            lines.append(f"uor_alignment_last_check {self._last_check_time}")

        # Version info as labels
        local = self._local_version or "unknown"
        upstream = self._upstream_version or "unknown"
        lines.append("# HELP uor_alignment_info UOR alignment version info")
        lines.append("# TYPE uor_alignment_info gauge")
        lines.append(
            f'uor_alignment_info{{local="{local}",upstream="{upstream}"}} 1'
        )

        return "\n".join(lines) + "\n"

    def get_status(self) -> dict:
        """Get current alignment status as dict."""
        return {
            "local_version": self._local_version,
            "upstream_version": self._upstream_version,
            "drift_detected": self._drift_detected,
            "artifacts_fresh": self._artifacts_fresh,
            "validation_status": self._validation_status,
            "last_check_time": self._last_check_time,
        }


# Global instance
_alignment_metrics = UORAlignmentMetrics()


def get_uor_alignment_metrics() -> UORAlignmentMetrics:
    """Get the global UOR alignment metrics instance."""
    return _alignment_metrics
