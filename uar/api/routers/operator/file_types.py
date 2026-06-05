"""File type whitelist read-only router for operator dashboard."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.file_type_guard import (
    get_allowed_extensions,
    get_blocked_extensions,
)
from uar.api.routers.operator.common import require_operator

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/file-types")
async def get_file_types(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Return current file type whitelist and blocklist."""
    require_operator(credentials)
    allowed = sorted(get_allowed_extensions())
    blocked = sorted(get_blocked_extensions())
    return {
        "allowed_extensions": allowed,
        "blocked_extensions": blocked,
        "whitelist_env_set": bool(allowed),
        "blocklist_env_set": bool(blocked),
    }
