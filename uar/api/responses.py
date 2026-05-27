"""Shared JSON response builders for API endpoints.

Eliminates repetitive JSONResponse construction across server.py
and other endpoint modules.
"""

from typing import Any, Optional
from fastapi.responses import JSONResponse


def error_response(
    status_code: int,
    error: str,
    message: str,
    request_id: Optional[str] = None,
    **extra: Any,
) -> JSONResponse:
    """Build a standard JSON error response.

    Args:
        status_code: HTTP status code
        error: Short error code string
        message: Human-readable error description
        request_id: Optional request ID for tracing
        **extra: Additional fields merged into the response body

    Returns:
        JSONResponse with standardized error payload
    """
    content: dict[str, Any] = {"error": error, "message": message}
    if request_id is not None:
        content["request_id"] = request_id
    content.update(extra)
    return JSONResponse(status_code=status_code, content=content)


def error_detail_response(
    status_code: int,
    error: str,
    message: str,
    request_id: Optional[str] = None,
    **extra: Any,
) -> JSONResponse:
    """Build a JSON error response wrapped in ``detail`` key.

    Used by exception handlers that need FastAPI-compatible
    ``{detail: {...}}`` structure.
    """
    content: dict[str, Any] = {"error": error, "message": message}
    if request_id is not None:
        content["request_id"] = request_id
    content.update(extra)
    return JSONResponse(status_code=status_code, content={"detail": content})
