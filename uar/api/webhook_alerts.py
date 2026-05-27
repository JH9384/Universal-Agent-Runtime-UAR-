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
        """Send alert to a single webhook endpoint."""
        payload = {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "timestamp": time.time() if hasattr(time, "time") else None,
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


# Global instance
_alerter = WebhookAlerter()


def get_webhook_alerter() -> WebhookAlerter:
    """Get the global webhook alerter instance."""
    return _alerter
