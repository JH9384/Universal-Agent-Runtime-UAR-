"""UAR Core Exception Classes"""

from typing import Optional


class UARError(Exception):
    """Base exception class for all UAR errors"""
    pass


class ValidationError(UARError):
    """Raised when input validation fails"""
    def __init__(self, message: str, field: Optional[str] = None):
        self.field = field
        super().__init__(message)


class SkillNotFoundError(UARError):
    """Raised when a requested skill is not found in the registry"""
    def __init__(self, skill_name: str):
        self.skill_name = skill_name
        super().__init__(f"Skill '{skill_name}' not found in registry")


class SkillExecutionError(UARError):
    """Raised when skill execution fails"""
    def __init__(self, skill_name: str, original_error: Exception):
        self.skill_name = skill_name
        self.original_error = original_error
        super().__init__(f"Skill '{skill_name}' execution failed: {original_error}")


class TimeoutError(UARError):
    """Raised when operation times out"""
    def __init__(self, timeout_seconds: float):
        self.timeout_seconds = timeout_seconds
        super().__init__(f"Operation timed out after {timeout_seconds} seconds")


class PathSecurityError(UARError):
    """Raised when path access violates security constraints"""
    def __init__(self, path: str, reason: str):
        self.path = path
        self.reason = reason
        super().__init__(f"Path security violation for '{path}': {reason}")


class EventContractError(UARError):
    """Raised when event contract is violated"""
    pass


class PersistenceError(UARError):
    """Raised when persistence operations fail"""
    pass
