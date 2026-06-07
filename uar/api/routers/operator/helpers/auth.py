"""Auth and audit helpers for operator workflow routers."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import auth_middleware

logger = logging.getLogger(__name__)

# Operator/admin tiers that may perform destructive admin actions
_ADMIN_TIERS = frozenset({"operator", "admin", "developer"})


def require_operator(
    credentials: Optional[HTTPAuthorizationCredentials],
) -> Optional[Dict[str, Any]]:
    """Authenticate and require operator-or-higher tier.

    Returns user_info dict on success, raises 403 on insufficient tier.
    """
    user_info = auth_middleware(credentials)
    if user_info is None:
        # Anonymous — not allowed for admin endpoints
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "Authentication required",
                "error_code": "AUTH_REQUIRED",
                "message": "Admin endpoints require a valid API key.",
            },
        )
    tier = user_info.get("tier", "")
    if tier not in _ADMIN_TIERS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "Insufficient privileges",
                "error_code": "FORBIDDEN",
                "message": (
                    f"Tier '{tier}' is not authorised for admin operations."
                ),
            },
        )
    return user_info


def audit_admin_action(
    *,
    user_info: Optional[Dict[str, Any]],
    action: str,
    resource: str,
    outcome: str,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
) -> None:
    """Write an immutable audit record for an admin action.

    Also fires webhook alerts for critical outcomes (failure,
    auth denial, deletion) so on-call engineers are paged.

    Non-blocking: exceptions are swallowed so the main operation
    is never impeded by audit-log I/O or webhook delivery.
    """
    actor = (
        user_info.get("user", "unknown")
        if user_info
        else "unknown"
    )
    try:
        from uar.core.audit import get_audit_logger

        get_audit_logger().write(
            event_type="admin_action",
            actor=actor,
            action=action,
            resource=resource,
            outcome=outcome,
            details=details,
            request_id=request_id,
        )
    except Exception as exc:
        logger.warning("audit_admin_action audit log failed: %s", exc)

    # Fire webhook for critical events
    try:
        if outcome in ("failure", "denied", "not_found") or \
                "DELETE" in action:
            from uar.api.webhook_alerts import get_webhook_alerter

            alerter = get_webhook_alerter()
            alerter.alert_admin_action(
                actor=actor,
                action=action,
                resource=resource,
                outcome=outcome,
                details=details,
            )
    except Exception as exc:
        logger.warning("audit_admin_action webhook alert failed: %s", exc)
