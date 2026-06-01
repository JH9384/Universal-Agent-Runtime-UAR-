"""Slack / Discord notification formatters for UAR webhook alerts.

Converts generic webhook payloads into platform-specific formats.
"""
from __future__ import annotations

import json
from typing import Any, Dict, Optional


def format_slack(
    alert_type: str,
    severity: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Format alert for Slack incoming webhook.

    Returns a Slack-compatible payload dict.
    """
    color_map = {
        "info": "#36a64f",
        "warning": "#ff9900",
        "error": "#ff0000",
    }
    color = color_map.get(severity, "#999999")

    fields = []
    if data:
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, default=str)[:100]
            fields.append(
                {
                    "title": str(k),
                    "value": str(v),
                    "short": len(str(v)) < 50,
                }
            )

    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"[{severity.upper()}] {alert_type}",
                "text": message,
                "fields": fields[:10],  # Slack limits
                "footer": "UAR Alert",
                "ts": data.get("timestamp") if data else None,
            }
        ]
    }
    return payload


def format_discord(
    alert_type: str,
    severity: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Format alert for Discord webhook.

    Returns a Discord-compatible payload dict.
    """
    color_map = {
        "info": 0x36A64F,
        "warning": 0xFF9900,
        "error": 0xFF0000,
    }
    color = color_map.get(severity, 0x999999)

    fields = []
    if data:
        for k, v in data.items():
            if isinstance(v, (list, dict)):
                v = json.dumps(v, default=str)[:100]
            fields.append(
                {
                    "name": str(k)[:256],
                    "value": str(v)[:1024],
                    "inline": len(str(v)) < 50,
                }
            )

    payload = {
        "embeds": [
            {
                "title": f"[{severity.upper()}] {alert_type}",
                "description": message,
                "color": color,
                "fields": fields[:25],  # Discord limit
                "footer": {"text": "UAR Alert"},
                "timestamp": (
                    data.get("timestamp") if data else None
                ),
            }
        ]
    }
    return payload


def format_notification(
    platform: str,
    alert_type: str,
    severity: str,
    message: str,
    data: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Dispatch to the correct formatter by platform.

    platform: 'slack', 'discord', or 'generic'.
    """
    if platform == "slack":
        return format_slack(alert_type, severity, message, data)
    if platform == "discord":
        return format_discord(alert_type, severity, message, data)
    if platform == "generic":
        return {
            "alert_type": alert_type,
            "severity": severity,
            "message": message,
            "data": data or {},
        }
    return None
