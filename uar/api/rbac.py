"""RBAC (Role-Based Access Control) for UAR API.

Tiers: admin, operator, viewer.
Permissions map to Mission Control data access.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Callable, Dict, Optional, Set

from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import auth_middleware

TIER_HIERARCHY = ["viewer", "operator", "admin"]

# permission -> minimum tier required
PERMISSIONS: Dict[str, str] = {
    # Mission Control read
    "mc.read": "viewer",
    # Mission Control recommendations
    "mc.recommendations": "viewer",
    # Mission Control analytics
    "mc.analytics": "operator",
    # Mission Control history
    "mc.history": "viewer",
    # Mission Control admin features
    "mc.admin": "admin",
    # Run execution
    "run.execute": "operator",
    # Run replay
    "run.replay": "viewer",
    # Outcome recording
    "outcome.record": "operator",
    # Bulk outcome import
    "outcome.bulk": "admin",
    # Trust export
    "trust.export": "operator",
    # Audit log
    "audit.read": "admin",
    # Burn-in control
    "burnin.control": "admin",
    # Webhook config
    "webhook.config": "admin",
    # Topology analytics
    "topology.read": "operator",
    # Chaos engineering
    "chaos.run": "admin",
}


def _tier_level(tier: Optional[str]) -> int:
    """Return numeric level for tier (higher = more access)."""
    if tier is None:
        return -1
    try:
        return TIER_HIERARCHY.index(tier)
    except ValueError:
        return -1


def has_permission(
    user_info: Optional[Dict[str, Any]], permission: str
) -> bool:
    """Check if user has the required permission."""
    if user_info is None:
        return False
    min_tier = PERMISSIONS.get(permission, "admin")
    return _tier_level(user_info.get("tier")) >= _tier_level(min_tier)


def require_permission(permission: str):
    """Decorator for FastAPI route handlers.

    Usage:
        @router.get("/api/uar/some-endpoint")
        @require_permission("mc.read")
        async def my_endpoint(credentials: ... = Depends(security)):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            credentials: Optional[HTTPAuthorizationCredentials] = kwargs.get(
                "credentials"
            )
            if credentials is None:
                for arg in args:
                    if isinstance(arg, HTTPAuthorizationCredentials):
                        credentials = arg
                        break
            user_info = auth_middleware(credentials)
            if user_info is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail={
                        "error": "authentication_required",
                        "message": "Authentication required",
                    },
                )
            if not has_permission(user_info, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "forbidden",
                        "permission": permission,
                        "message": (
                            f"Tier '{user_info.get('tier')}' "
                            f"lacks permission '{permission}'"
                        ),
                    },
                )
            return await func(*args, **kwargs)
        return wrapper
    return decorator


class PermissionChecker:
    """Helper for checking multiple permissions at once."""

    def __init__(self, user_info: Optional[Dict[str, Any]]):
        self._user = user_info
        self._tier = user_info.get("tier") if user_info else None
        self._level = _tier_level(self._tier)

    def can(self, permission: str) -> bool:
        return has_permission(self._user, permission)

    def tier(self) -> Optional[str]:
        return self._tier

    def filter_fields(
        self, data: Dict[str, Any], allowed: Set[str]
    ) -> Dict[str, Any]:
        """Filter dict keys based on allowed set."""
        return {k: v for k, v in data.items() if k in allowed}
