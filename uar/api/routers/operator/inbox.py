"""Recommendation Inbox router."""

from __future__ import annotations

import logging
import time
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from uar.api.middleware import auth_middleware
from uar.api.routers.operator.common import (
    _generate_inbox_items,
    _load_all_inbox_items,
    _persist_inbox_item,
)

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)
router = APIRouter()


@router.get("/api/uar/inbox")
async def get_inbox(
    status: Optional[str] = Query(None),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> List[dict]:
    """List recommendation inbox items."""
    auth_middleware(credentials)
    items = _generate_inbox_items()
    if status:
        items = [i for i in items if i.get("status") == status]
    return items


@router.put("/api/uar/inbox/{item_id}")
async def update_inbox_item(
    item_id: str,
    body: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Update an inbox item (status, assignment, notes)."""
    auth_middleware(credentials)
    for item in _load_all_inbox_items():
        if item.get("id") == item_id:
            for field in ("status", "assigned_to", "notes"):
                if field in body:
                    item[field] = body[field]
            item["updated_at"] = int(time.time())
            _persist_inbox_item(item)
            return item
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Inbox item not found",
    )
