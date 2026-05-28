"""Tests for FastAPI exception handlers.

Covers register_exception_handlers.
"""

from fastapi import FastAPI

from uar.api.exception_handlers import register_exception_handlers
from uar.core.exceptions import ValidationError, PathSecurityError, UARError


class TestRegisterExceptionHandlers:
    """Exception handler registration."""

    def test_registers_all_handlers(self):
        app = FastAPI()
        register_exception_handlers(app)
        # Check that handlers were registered
        # The exception handlers are stored in app.exception_handlers
        assert len(app.exception_handlers) > 0

    def test_validation_error_handler(self):
        app = FastAPI()
        register_exception_handlers(app)
        handler = app.exception_handlers.get(ValidationError)
        assert handler is not None

    def test_path_security_error_handler(self):
        app = FastAPI()
        register_exception_handlers(app)
        handler = app.exception_handlers.get(PathSecurityError)
        assert handler is not None

    def test_uar_error_handler(self):
        app = FastAPI()
        register_exception_handlers(app)
        handler = app.exception_handlers.get(UARError)
        assert handler is not None
