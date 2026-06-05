"""Webhook Alerting System for UOR drift and critical events.

Supports configurable webhooks for alignment drift, validation failures,
and other operational alerts.
"""
from __future__ import annotations

import json
import logging
import os
import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class WebhookAlerter:
    """Manages webhook alerts for operational events."""

    def __init__(self):
        self._endpoints: List[str] = self._load_endpoints()
        self._enabled = bool(self._endpoints)

    def _load_endpoints(self) -> List[str]:
        """Load webhook endpoints from environment."""
        endpoints = os.getenv("UOR_WEBHOOK_ENDPOINTS", "")
        if not endpoints:
            return []
        valid = []
        for e in endpoints.split(","):
            e = e.strip()
            if not e:
                continue
            parsed = urlparse(e)
            if parsed.scheme not in ("http", "https"):
                logger.warning("Ignoring invalid webhook endpoint: %s", e)
                continue
            valid.append(e)
        return valid

    def _send_alert(
        self,
        endpoint: str,
        alert_type: str,
        severity: str,
        message: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Send alert to a single webhook endpoint.

        Detects Slack / Discord hostnames and formats the payload
        appropriately so generic UAR alerts render correctly.
        """
        # Track alert accuracy
        try:
            from uar.api.alert_tracker import get_alert_tracker
            tracker = get_alert_tracker()
            tracker.record_fired(alert_type, severity, message, data)
        except Exception as _exc:
            logger.debug("Webhook alert tracking failed: %s", _exc)

        # Detect platform and format payload
        platform = "generic"
        if "hooks.slack.com" in endpoint:
            platform = "slack"
        elif "discord.com/api/webhooks" in endpoint:
            platform = "discord"

        if platform != "generic":
            from uar.api.notifications import format_notification

            payload = format_notification(
                platform, alert_type, severity, message, data
            )
        else:
            payload = {
                "alert_type": alert_type,
                "severity": severity,
                "message": message,
                "timestamp": time.time(),
                "source": "uar",
                "data": data or {},
            }

        try:
            req = Request(
                endpoint,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urlopen(req, timeout=10) as resp:
                return resp.status == 200
        except (OSError, ValueError):
            logger.exception("Failed to send webhook alert to %s", endpoint)
            return False

    def alert_alignment_drift(
        self,
        local_version: str,
        upstream_version: str,
        auto_refresh: bool = False,
    ) -> None:
        """Send alert for alignment drift detected."""
        if not self._enabled:
            return

        message = (
            f"UOR alignment drift detected: "
            f"local={local_version}, upstream={upstream_version}"
        )
        data = {
            "local_version": local_version,
            "upstream_version": upstream_version,
            "auto_refresh_enabled": auto_refresh,
        }

        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "alignment_drift",
                "warning",
                message,
                data,
            )

    def alert_validation_failure(
        self,
        tag: str,
        error: str,
    ) -> None:
        """Send alert for validation failure."""
        if not self._enabled:
            return

        message = f"UOR artifact validation failed for {tag}: {error}"
        data = {"tag": tag, "error": error}

        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "validation_failure",
                "error",
                message,
                data,
            )

    def alert_auto_refresh(
        self,
        from_version: str,
        to_version: str,
        success: bool,
    ) -> None:
        """Send alert for auto-refresh attempt."""
        if not self._enabled:
            return

        if success:
            message = (
                f"UOR artifacts auto-refreshed: "
                f"{from_version} -> {to_version}"
            )
            severity = "info"
        else:
            message = (
                f"UOR artifacts auto-refresh FAILED: "
                f"{from_version} -> {to_version}"
            )
            severity = "error"

        data = {
            "from_version": from_version,
            "to_version": to_version,
            "success": success,
        }

        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "auto_refresh",
                severity,
                message,
                data,
            )

    # Ω-7B.1: Trust system alerts
    def alert_divergence(
        self,
        count: int,
        top_cases: list[dict],
    ) -> None:
        """Send alert when divergence cases are detected."""
        if not self._enabled:
            return
        message = (
            f"Trust divergence detected: "
            f"{count} recommendation(s) with confidence/trust mismatch"
        )
        data = {"count": count, "top_cases": top_cases}
        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "divergence",
                "warning",
                message,
                data,
            )

    def alert_drift(
        self,
        recipe_type: str,
        drift_penalty: float,
        trust_score: float,
    ) -> None:
        """Send alert when a recommendation type shows drift."""
        if not self._enabled:
            return
        message = (
            f"Trust drift: {recipe_type} penalty={drift_penalty:.3f} "
            f"trust={trust_score:.3f}"
        )
        data = {
            "recipe_type": recipe_type,
            "drift_penalty": drift_penalty,
            "trust_score": trust_score,
        }
        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "drift",
                "warning",
                message,
                data,
            )

    def alert_trust_drop(
        self,
        recipe_type: str,
        old_score: float,
        new_score: float,
    ) -> None:
        """Send alert when trust score drops significantly."""
        if not self._enabled:
            return
        delta = old_score - new_score
        message = (
            f"Trust drop: {recipe_type} fell from "
            f"{old_score:.3f} to {new_score:.3f} (-{delta:.3f})"
        )
        data = {
            "recipe_type": recipe_type,
            "old_score": old_score,
            "new_score": new_score,
            "delta": delta,
        }
        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "trust_drop",
                "error" if delta > 0.3 else "warning",
                message,
                data,
            )

    # Operational alerts
    def alert_burnin_failure(
        self,
        phase: str,
        error: str,
        duration_seconds: int,
    ) -> None:
        """Send alert when burn-in fails."""
        if not self._enabled:
            return
        message = (
            f"Burn-in failed at phase '{phase}' "
            f"after {duration_seconds}s: {error}"
        )
        data = {
            "phase": phase,
            "error": error,
            "duration_seconds": duration_seconds,
        }
        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "burnin_failure",
                "error",
                message,
                data,
            )

    def alert_admin_action(
        self,
        actor: str,
        action: str,
        resource: str,
        outcome: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Send alert when a critical admin action occurs."""
        if not self._enabled:
            return
        message = (
            f"Admin action by {actor}: {action} on {resource} "
            f"→ outcome={outcome}"
        )
        data = {
            "actor": actor,
            "action": action,
            "resource": resource,
            "outcome": outcome,
            "details": details or {},
        }
        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "admin_action",
                "error" if outcome in ("failure", "denied") else "warning",
                message,
                data,
            )

    def alert_system_health(
        self,
        cpu_percent: float,
        memory_percent: float,
        disk_percent: float,
    ) -> None:
        """Send alert when system health crosses thresholds."""
        if not self._enabled:
            return
        severity = "info"
        if cpu_percent > 90 or memory_percent > 90 or disk_percent > 90:
            severity = "error"
        elif cpu_percent > 75 or memory_percent > 75 or disk_percent > 80:
            severity = "warning"
        if severity == "info":
            return  # No alert for healthy systems
        message = (
            f"System health: CPU={cpu_percent:.1f}% "
            f"MEM={memory_percent:.1f}% DISK={disk_percent:.1f}%"
        )
        data = {
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
            "disk_percent": disk_percent,
        }
        for endpoint in self._endpoints:
            self._send_alert(
                endpoint,
                "system_health",
                severity,
                message,
                data,
            )


# Global instance
_alerter = WebhookAlerter()


def get_webhook_alerter() -> WebhookAlerter:
    """Get the global webhook alerter instance."""
    return _alerter
