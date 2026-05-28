"""FastAPI exception handlers for UAR domain exceptions."""

from fastapi import FastAPI, status
from fastapi.responses import JSONResponse

from uar.core.exceptions import PathSecurityError, UARError, ValidationError


def register_exception_handlers(app: FastAPI) -> None:
    """Attach UAR exception handlers to a FastAPI application."""

    @app.exception_handler(ValidationError)
    async def validation_error_handler(request, exc):
        field = getattr(exc, "field", None)
        if field == "input_path":
            message = "Invalid path provided"
        elif field == "goal":
            message = "Invalid goal provided"
        elif field == "skills":
            message = "Invalid skills provided"
        elif field == "timeout_seconds":
            message = "Invalid timeout provided"
        elif field == "execution_order":
            message = "Invalid execution order provided"
        else:
            message = "Invalid input provided"
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": {
                    "error": "Validation error",
                    "code": exc.code.value,
                    "message": message,
                    "field": field,
                }
            },
        )

    @app.exception_handler(PathSecurityError)
    async def path_security_error_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "detail": {
                    "error": "Path security violation",
                    "code": exc.code.value,
                    "message": "Invalid path provided",
                    "field": "input_path",
                }
            },
        )

    @app.exception_handler(UARError)
    async def uar_error_handler(request, exc):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "detail": {
                    "error": "Internal error",
                    "code": exc.code.value,
                    "message": "An internal error occurred",
                }
            },
        )
