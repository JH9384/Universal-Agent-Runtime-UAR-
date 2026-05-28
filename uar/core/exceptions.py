"""UAR Core Exception Classes"""

from enum import Enum
from typing import Optional


class ErrorCode(str, Enum):
    """Machine-readable error codes for all UAR errors."""

    VALIDATION = "VALIDATION"
    PATH_SECURITY = "PATH_SECURITY"
    SKILL_NOT_FOUND = "SKILL_NOT_FOUND"
    SKILL_EXECUTION = "SKILL_EXECUTION"
    SKILL_TIMEOUT = "SKILL_TIMEOUT"
    RATE_LIMITED = "RATE_LIMITED"
    EXTERNAL_DOWN = "EXTERNAL_DOWN"
    CONFIG_INVALID = "CONFIG_INVALID"
    EVENT_CONTRACT = "EVENT_CONTRACT"
    PERSISTENCE = "PERSISTENCE"
    INTERNAL = "INTERNAL"


class UARError(Exception):
    """Base exception class for all UAR errors."""

    code: ErrorCode = ErrorCode.INTERNAL


class ValidationError(UARError):
    """Raised when input validation fails."""

    code = ErrorCode.VALIDATION

    _FIELD_MESSAGES: dict[Optional[str], str] = {
        "goal": (
            "Invalid goal. Please provide a clear goal "
            "description (3-10,000 characters)."
        ),
        "skills": (
            "Invalid skills. Please check that the skills "
            "are available in the system."
        ),
        "input_path": (
            "Invalid path provided"
        ),
        "timeout_seconds": (
            "Invalid timeout. Please provide a timeout "
            "between 1 and 300 seconds."
        ),
        "execution_order": (
            "Invalid execution order. Please check that "
            "all skills and recipes are valid."
        ),
    }

    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message)

    @property
    def user_message(self) -> str:
        """Return a user-friendly message based on the invalid field."""
        return self._FIELD_MESSAGES.get(self.field, "Invalid input provided")


class SkillNotFoundError(UARError):
    """Raised when a requested skill is not found in the registry."""

    code = ErrorCode.SKILL_NOT_FOUND

    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        super().__init__(f"Skill '{skill_name}' not found in registry")


class SkillExecutionError(UARError):
    """Raised when skill execution fails."""

    code = ErrorCode.SKILL_EXECUTION

    def __init__(self, skill_name: str, original_error: Exception):
        self.skill_name = skill_name
        self.original_error = original_error
        super().__init__(
            f"Skill '{skill_name}' execution failed: {original_error}"
        )


class TimeoutError(UARError):
    """Raised when operation times out."""

    code = ErrorCode.SKILL_TIMEOUT

    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(
            f"Operation timed out after {timeout_seconds} seconds"
        )


class PathSecurityError(UARError):
    """Raised when path access violates security constraints."""

    code = ErrorCode.PATH_SECURITY

    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__("Path security violation")


class EventContractError(UARError):
    """Raised when event contract is violated."""

    code = ErrorCode.EVENT_CONTRACT


class ExternalServiceError(UARError):
    """Raised when an external service (Ollama, GraphRAG, Autonomi) is unreachable."""  # noqa: E501

    code = ErrorCode.EXTERNAL_DOWN

    def __init__(self, service: str, detail: str = ""):
        self.service = service
        super().__init__(
            f"External service '{service}' unavailable{f': {detail}' if detail else ''}"  # noqa: E501
        )


class ConfigInvalidError(UARError):
    """Raised when configuration is invalid."""

    code = ErrorCode.CONFIG_INVALID

    def __init__(self, message: str):
        super().__init__(message)


class PersistenceError(UARError):
    """Raised when persistence operations fail"""

    code = ErrorCode.PERSISTENCE
