"""Tests verifying all UAR custom exceptions inherit from UARError."""

from uar.core.exceptions import UARError, ErrorCode
from uar.core.safe_eval import SafeEvalError, SafeEvalNodeError, SafeEvalNameError, SafeEvalAttrError
from uar.core.crewai_real import CrewAIRealError
from uar.objects.sandbox import SandboxError
from uar.core.circuit_breaker import CircuitBreakerOpenError
from uar.compat.uor_address import UORAddressError


class TestExceptionHierarchy:
    """All custom exceptions must inherit from UARError for consistent handling."""

    def test_safe_eval_error_is_uar_error(self):
        exc = SafeEvalError("bad expr")
        assert isinstance(exc, UARError)
        assert exc.code == ErrorCode.VALIDATION

    def test_safe_eval_node_error_is_uar_error(self):
        exc = SafeEvalNodeError("bad node")
        assert isinstance(exc, UARError)
        assert isinstance(exc, SafeEvalError)

    def test_safe_eval_name_error_is_uar_error(self):
        exc = SafeEvalNameError("bad name")
        assert isinstance(exc, UARError)
        assert isinstance(exc, SafeEvalError)

    def test_safe_eval_attr_error_is_uar_error(self):
        exc = SafeEvalAttrError("bad attr")
        assert isinstance(exc, UARError)
        assert isinstance(exc, SafeEvalError)

    def test_crew_ai_real_error_is_uar_error(self):
        exc = CrewAIRealError("crew failed")
        assert isinstance(exc, UARError)
        assert exc.code == ErrorCode.SKILL_EXECUTION

    def test_sandbox_error_is_uar_error(self):
        exc = SandboxError("sandbox failed")
        assert isinstance(exc, UARError)
        assert exc.code == ErrorCode.VALIDATION

    def test_circuit_breaker_open_error_is_uar_error(self):
        exc = CircuitBreakerOpenError("cb")
        assert isinstance(exc, UARError)
        assert exc.code == ErrorCode.EXTERNAL_DOWN

    def test_uor_address_error_is_uar_error(self):
        exc = UORAddressError("address failed")
        assert isinstance(exc, UARError)
        assert exc.code == ErrorCode.VALIDATION
