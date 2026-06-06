"""Shared JSON response builders for API endpoints.

T9 — API Normalization: standardized success / error envelopes,
list pagination, and version headers.
"""

from typing import Any, Dict, List, Optional

from fastapi.responses import JSONResponse


def success_response(
    data: Any = None,
    *,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> JSONResponse:
    """Build a standard JSON success response.

    Envelope::

        {
          "data": <payload>,
          "meta": {"timestamp": ...}  # optional
        }

    Args:
        data: Payload to return under the ``data`` key.
        meta: Optional metadata dict merged into ``meta``.
        status_code: HTTP status code.

    Returns:
        JSONResponse with normalized success envelope.
    """
    content: dict[str, Any] = {"data": data}
    _meta: dict[str, Any] = meta.copy() if meta else {}
    if _meta:
        content["meta"] = _meta
    return JSONResponse(status_code=status_code, content=content)


def list_response(
    items: List[Any],
    *,
    total: Optional[int] = None,
    page: Optional[int] = None,
    page_size: Optional[int] = None,
    next_cursor: Optional[str] = None,
    meta: Optional[Dict[str, Any]] = None,
    status_code: int = 200,
) -> JSONResponse:
    """Build a standard paginated list response.

    Supports both offset (page / page_size) and cursor-based
    (next_cursor) pagination styles.

    Envelope::

        {
          "data": {
            "items": [...],
            "total": N,
            "page": 1,
            "page_size": 20,
            "next_cursor": "abc..."
          },
          "meta": {...}
        }
    """
    payload = {
        "items": items,
        "total": total if total is not None else len(items),
    }
    if page is not None:
        payload["page"] = page
    if page_size is not None:
        payload["page_size"] = page_size
    if next_cursor is not None:
        payload["next_cursor"] = next_cursor
    _meta = meta.copy() if meta else {}
    content: dict[str, Any] = {"data": payload}
    if _meta:
        content["meta"] = _meta
    return JSONResponse(status_code=status_code, content=content)


def error_response(
    status_code: int,
    error: str,
    message: str,
    request_id: Optional[str] = None,
    code: Optional[str] = None,
    **extra: Any,
) -> JSONResponse:
    """Build a standard JSON error response.

    Normalized envelope::

        {
          "error": "short_code",
          "message": "Human readable",
          "code": "DOMAIN_001",   # optional
          "request_id": "uuid"  # optional
        }

    Args:
        status_code: HTTP status code
        error: Short error code string
        message: Human-readable error description
        request_id: Optional request ID for tracing
        code: Optional machine-readable error code
        **extra: Additional fields merged into the response body

    Returns:
        JSONResponse with standardized error payload
    """
    content: dict[str, Any] = {"error": error, "message": message}
    if code is not None:
        content["code"] = code
    if request_id is not None:
        content["request_id"] = request_id
    content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


def error_detail_response(
    status_code: int,
    error: str,
    message: str,
    request_id: Optional[str] = None,
    code: Optional[str] = None,
    **extra: Any,
) -> JSONResponse:
    """Build a JSON error response wrapped in ``detail`` key.

    Used by exception handlers that need FastAPI-compatible
    ``{detail: {...}}`` structure.
    """
    content: dict[str, Any] = {"error": error, "message": message}
    if code is not None:
        content["code"] = code
    if request_id is not None:
        content["request_id"] = request_id
    content.update(extra)
    return JSONResponse(status_code=status_code, content={"detail": content})
