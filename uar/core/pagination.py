"""Cursor-based pagination for large skill results.

Provides ``CursorPaginator`` and ``PaginatedResponse`` for chunking
large result sets (e.g. ``graphrag_query``, ``doc_ingest``).

Usage in a skill:
    from uar.core.pagination import CursorPaginator

    def my_skill(ctx):
        results = [...]  # large list
        paginator = CursorPaginator(results, page_size=20)
        return paginator.first_page()

Clients then pass ``?cursor=<token>`` to paginate.
"""

import base64
import hashlib
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class CursorToken:
    """Opaque cursor token decoded from base64 JSON."""

    offset: int
    page_size: int
    checksum: str  # SHA-256 of the original data snapshot
    extra: Dict[str, Any]

    def encode(self) -> str:
        """Return a URL-safe base64-encoded string."""
        payload = {
            "o": self.offset,
            "s": self.page_size,
            "c": self.checksum,
            "e": self.extra,
        }
        raw = json.dumps(payload, separators=(",", ":")).encode()
        return base64.urlsafe_b64encode(raw).decode().rstrip("=")

    @classmethod
    def decode(cls, token: str) -> "CursorToken":
        """Decode a cursor token."""
        # Pad base64
        padding = 4 - len(token) % 4
        if padding != 4:
            token += "=" * padding
        raw = base64.urlsafe_b64decode(token.encode())
        payload = json.loads(raw)
        return cls(
            offset=payload["o"],
            page_size=payload["s"],
            checksum=payload["c"],
            extra=payload.get("e", {}),
        )


@dataclass
class PaginatedResponse(Generic[T]):
    """Standard paginated response shape."""

    data: List[T]
    total: int
    page_size: int
    next_cursor: Optional[str] = None
    previous_cursor: Optional[str] = None
    has_more: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to a plain dict for JSON serialization."""
        return {
            "data": self.data,
            "total": self.total,
            "page_size": self.page_size,
            "next_cursor": self.next_cursor,
            "previous_cursor": self.previous_cursor,
            "has_more": self.has_more,
        }


class CursorPaginator(Generic[T]):
    """Cursor-based paginator for in-memory result lists.

    Thread-safe for read-only data.  If the underlying data mutates,
    checksum mismatches will trigger ``ValueError``.
    """

    def __init__(
        self,
        data: List[T],
        *,
        page_size: int = 20,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._data = data
        self._page_size = max(1, page_size)
        self._checksum = self._compute_checksum(data)
        self._extra = extra or {}

    @staticmethod
    def _compute_checksum(data: List[T]) -> str:
        """Stable checksum for detecting data mutations."""
        try:
            payload = json.dumps(data, sort_keys=True, default=str)
        except (TypeError, ValueError):
            # Non-serializable data: hash the reprs
            payload = repr(data)
        return hashlib.sha256(payload.encode()).hexdigest()[:16]

    def _verify_checksum(self, token: CursorToken) -> None:
        if token.checksum != self._checksum:
            raise ValueError(
                "Cursor checksum mismatch — data changed since first page"
            )

    def first_page(self) -> PaginatedResponse[T]:
        """Return the first page and a cursor for the next page."""
        return self.page_at(0)

    def page_at(self, offset: int) -> PaginatedResponse[T]:
        """Return the page starting at *offset*."""
        total = len(self._data)
        end = min(offset + self._page_size, total)
        page_data = self._data[offset:end]

        next_cursor: Optional[str] = None
        if end < total:
            next_cursor = CursorToken(
                offset=end,
                page_size=self._page_size,
                checksum=self._checksum,
                extra=self._extra,
            ).encode()

        prev_cursor: Optional[str] = None
        if offset > 0:
            prev_offset = max(0, offset - self._page_size)
            prev_cursor = CursorToken(
                offset=prev_offset,
                page_size=self._page_size,
                checksum=self._checksum,
                extra=self._extra,
            ).encode()

        return PaginatedResponse(
            data=page_data,
            total=total,
            page_size=self._page_size,
            next_cursor=next_cursor,
            previous_cursor=prev_cursor,
            has_more=next_cursor is not None,
        )

    def next_page(self, cursor: str) -> PaginatedResponse[T]:
        """Return the page following *cursor*."""
        token = CursorToken.decode(cursor)
        self._verify_checksum(token)
        return self.page_at(token.offset)

    def all_pages(self) -> List[PaginatedResponse[T]]:
        """Return all pages as a list (useful for testing)."""
        pages = []
        current = self.first_page()
        pages.append(current)
        while current.next_cursor:
            current = self.next_page(current.next_cursor)
            pages.append(current)
        return pages


# ---------------------------------------------------------------------------
# Convenience helpers for skills
# ---------------------------------------------------------------------------

def maybe_paginate(
    data: List[T],
    cursor: Optional[str] = None,
    *,
    page_size: int = 20,
    extra: Optional[Dict[str, Any]] = None,
) -> PaginatedResponse[T]:
    """Create a paginator and return the requested page.

    If *cursor* is ``None``, returns the first page.
    """
    paginator = CursorPaginator(data, page_size=page_size, extra=extra)
    if cursor is None:
        return paginator.first_page()
    return paginator.next_page(cursor)
