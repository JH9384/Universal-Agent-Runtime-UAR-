"""Cursor-based pagination helpers (E7).

Opaque cursor format: base64(JSON({"last_id": <str>, "sort": <str>})).
This avoids exposing internal sort values and is trivial to extend
to composite cursors later.
"""

from __future__ import annotations

import base64
import json
from typing import Any, Dict, List, Optional, Tuple


def encode_cursor(last_id: str, sort_field: str = "run_id") -> str:
    """Encode a pagination cursor."""
    payload = json.dumps({"last_id": last_id, "sort": sort_field})
    return base64.urlsafe_b64encode(payload.encode()).decode().rstrip("=")


def decode_cursor(cursor: str) -> Optional[Dict[str, str]]:
    """Decode a pagination cursor. Returns None if invalid."""
    try:
        # Add padding back if needed
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = base64.urlsafe_b64decode(padded.encode()).decode()
        obj = json.loads(payload)
        if isinstance(obj, dict) and "last_id" in obj:
            return obj
    except Exception:
        pass
    return None


def paginate_cursor(
    items: List[Dict[str, Any]],
    *,
    cursor: Optional[str] = None,
    limit: int = 20,
    sort_key: str = "run_id",
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Apply cursor-based pagination to an in-memory list of dicts.

    Args:
        items: Full list of records (already filtered / ordered).
        cursor: Opaque cursor from a previous response.
        limit: Max items to return.
        sort_key: Field used for ordering and cursor anchoring.

    Returns:
        (page_items, next_cursor) where next_cursor is None when
        the returned page is the last one.
    """
    decoded = decode_cursor(cursor) if cursor else None
    if decoded:
        last_id = decoded.get("last_id")
        # Fast-forward past the cursor
        start_idx = 0
        for i, item in enumerate(items):
            if item.get(sort_key) == last_id:
                start_idx = i + 1
                break
        else:
            start_idx = 0  # cursor not found, start from beginning
        items = items[start_idx:]

    page = items[:limit]
    next_cursor: Optional[str] = None
    if len(items) > limit and page:
        last_item = page[-1]
        next_cursor = encode_cursor(
            last_item.get(sort_key, ""), sort_field=sort_key
        )
    return page, next_cursor
