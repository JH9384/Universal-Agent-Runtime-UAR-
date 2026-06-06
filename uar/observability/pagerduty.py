"""PagerDuty Events API v2 integration for UAR synthetic probing.

T8 — Synthetic Probing: sends trigger/resolve events to PagerDuty
when probes fail or recover.

Env vars:
  UAR_PAGERDUTY_ROUTING_KEY  — Integration key (required)
  UAR_PAGERDUTY_SEVERITY     — Default: critical
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Optional
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

_PAGERDUTY_EVENTS_URL = "https://events.pagerduty.com/v2/enqueue"


class PagerDutyNotifier:
    """Send PagerDuty Events API v2 trigger / resolve / acknowledge.

    Each probe scenario gets a unique ``dedup_key`` so repeated
    failures of the same probe are grouped and recovery auto-resolves.
    """

    def __init__(
        self,
        routing_key: Optional[str] = None,
        severity: Optional[str] = None,
    ) -> None:
        self._routing_key = routing_key or os.getenv(
            "UAR_PAGERDUTY_ROUTING_KEY", ""
        )
        self._severity = severity or os.getenv(
            "UAR_PAGERDUTY_SEVERITY", "critical"
        )
        self._enabled = bool(self._routing_key)

    def _dedup_key(self, scenario: str) -> str:
        return f"uar-probe-{scenario}"

    def trigger(
        self,
        summary: str,
        scenario: str,
        details: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Send a trigger event."""
        if not self._enabled:
            return False
        return self._send(
            "trigger",
            summary,
            scenario,
            details,
        )

    def resolve(
        self,
        summary: str,
        scenario: str,
        details: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Send a resolve event."""
        if not self._enabled:
            return False
        return self._send(
            "resolve",
            summary,
            scenario,
            details,
        )

    def _send(
        self,
        action: str,
        summary: str,
        scenario: str,
        details: Optional[dict[str, Any]],
    ) -> bool:
        payload = {
            "routing_key": self._routing_key,
            "event_action": action,
            "dedup_key": self._dedup_key(scenario),
            "payload": {
                "summary": summary,
                "severity": self._severity,
                "source": "uar-synthetic-probe",
                "custom_details": details or {},
            },
        }
        req = Request(
            _PAGERDUTY_EVENTS_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with urlopen(req, timeout=10) as resp:
                body = resp.read()
                logger.info(
                    "PagerDuty %s for %s: HTTP %d — %s",
                    action,
                    scenario,
                    resp.status,
                    body.decode("utf-8")[:200],
                )
                return True
        except Exception as exc:
            logger.error(
                "PagerDuty %s failed for %s: %s", action, scenario, exc
            )
            return False
