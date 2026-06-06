"""FastAPI exception handlers for UAR domain exceptions.

T9 — API Normalization: all domain exceptions produce the same
``{detail: {error, message, code, ...}}`` shape.
"""

from fastapi import FastAPI, status

from uar.api.responses import error_detail_response
from uar.core.exceptions import PathSecurityError, UARError, ValidationError


def register_exception_handlers(app: FastAPI) -> None:
    """Attach UAR exception handlers to a FastAPI application."""

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request, exc):
        field = getattr(exc, "field", None)
        return error_detail_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="validation_error",
            message=exc.user_message,
            code=exc.code.value,
            field=field,
        )

    @app.exception_handler(PathSecurityError)
    async def path_security_error_handler(request, exc):
        return error_detail_response(
            status_code=status.HTTP_400_BAD_REQUEST,
            error="path_security_violation",
            message="Invalid path provided",
            code=exc.code.value,
            field="input_path",
        )

    @app.exception_handler(UARError)
    async def uar_error_handler(request, exc):
        return error_detail_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error="internal_error",
            message="An internal error occurred",
            code=exc.code.value,
        )
