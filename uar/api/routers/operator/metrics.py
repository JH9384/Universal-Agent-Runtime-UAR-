"""Admin Prometheus metrics router.

Exports operator-facing metrics from the audit log and alert tracker
as Prometheus exposition format for scraping.
"""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.routers.operator.common import require_operator

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/metrics/admin")
async def get_admin_metrics(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> Response:
    """Return admin action and alert metrics in Prometheus text format.

    Designed to be scraped by Prometheus or Promtail sidecars.
    """
    require_operator(credentials)

    lines: list[str] = [
        '# HELP uar_admin_actions_total '
        'Admin mutation count by action and outcome',
        '# TYPE uar_admin_actions_total counter',
    ]

    # Audit log metrics — computed from in-memory recent events if available
    try:
        from uar.core.audit import get_audit_logger

        logger_instance = get_audit_logger()
        path = getattr(logger_instance, "path", None)
        if path and path.exists():
            # Count last 1k lines by action/outcome
            counts: dict[str, int] = {}
            with path.open("r", encoding="utf-8") as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        import json

                        rec = json.loads(line)
                        action = rec.get("action", "unknown")
                        outcome = rec.get("outcome", "unknown")
                        key = f'action="{action}",outcome="{outcome}"'
                        counts[key] = counts.get(key, 0) + 1
                    except Exception:
                        continue
            for key, total in counts.items():
                lines.append(
                    f"uar_admin_actions_total{{{key}}} {total}"
                )
    except Exception:
        logger.debug("Admin audit metrics collection failed")

    lines.extend([
        '',
        '# HELP uar_alerts_total Webhook alerts fired by type and severity',
        '# TYPE uar_alerts_total counter',
    ])

    # Alert tracker metrics
    try:
        from uar.api.alert_tracker import get_alert_tracker

        tracker = get_alert_tracker()
        by_type: dict[str, dict[str, int]] = {}
        for ev in tracker._pending:
            at = ev.get("alert_type", "unknown")
            sev = ev.get("severity", "unknown")
            if at not in by_type:
                by_type[at] = {}
            by_type[at][sev] = by_type[at].get(sev, 0) + 1
        for at, sevs in by_type.items():
            for sev, total in sevs.items():
                tag = f'alert_type="{at}",severity="{sev}"'
                lines.append(f"uar_alerts_total{{{tag}}} {total}")
    except Exception:
        logger.debug("Alert metrics collection failed")

    lines.append('')  # trailing newline
    return Response(
        media_type="text/plain; charset=utf-8",
        content="\n".join(lines),
    )
