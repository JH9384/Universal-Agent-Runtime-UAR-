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
    payload = {
        "items": items,
        "total": total if total is not None else len(items),
        "next_cursor": next_cursor,
    }
    if page is not None:
        payload["page"] = page
    if page_size is not None:
        payload["page_size"] = page_size
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
    content: dict[str, Any] = {"error": error, "message": message}
    if code is not None:
        content["code"] = code
    if request_id is not None:
        content["request_id"] = request_id
    content.update(extra)
    return JSONResponse(status_code=status_code, content={"detail": content})
