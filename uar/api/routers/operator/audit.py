"""Audit log verification endpoint.

T3 — Immutable Audit Logs: provides chain-verification
for compliance officers.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware

security = HTTPBearer(auto_error=False)

router = APIRouter()


@router.get("/api/uar/admin/audit/verify")
async def verify_audit_chain(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(
        security  # type: ignore[assignment]
    ),
) -> Dict[str, Any]:
    """Verify the integrity of the immutable audit log.

    Returns the hash-chain verification result. Any tampered or
    corrupted records are listed in *failures*.
    """
    # type: ignore[misc] — FastAPI injection
    user_info = auth_middleware(credentials)
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={
                "error": "authentication_required",
                "message": "Authentication required",
            },
        )

    from uar.core.audit import get_audit_logger

    logger = get_audit_logger()
    ok, failures = logger.verify_chain()
    return {
        "ok": ok,
        "record_count": _count_records(logger),
        "failures": failures,
        "failures_count": len(failures),
    }


def _count_records(logger) -> int:
    """Count total audit records."""
    if not logger.path.exists():
        return 0
    count = 0
    with logger.path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                count += 1
    return count
