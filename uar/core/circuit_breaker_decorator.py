"""Circuit breaker decorator for external service calls.

Provides a convenient decorator to wrap external service calls with
circuit breaker protection.
"""

from functools import wraps
from typing import Callable, Any
from .circuit_breaker import CircuitBreaker, CircuitBreakerOpenError
from .exceptions import SkillExecutionError
import logging
import threading

logger = logging.getLogger(__name__)

# Global circuit breaker instances for common services
_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_breakers_lock = threading.Lock()


def get_circuit_breaker(
    name: str,
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0,
    half_open_max: int = 1,
) -> CircuitBreaker:
    """Get or create a circuit breaker for a service.

    Args:
        name: Service name (e.g., 'ollama', 'openai', 'groq')
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds to wait before trying again
        half_open_max: Max calls allowed in half-open state

    Returns:
        CircuitBreaker instance
    """
    with _circuit_breakers_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                recovery_timeout=recovery_timeout,
                half_open_max=half_open_max,
            )
        return _circuit_breakers[name]


def with_circuit_breaker(
    service_name: str,
    failure_threshold: int = 3,
    recovery_timeout: float = 30.0,
    half_open_max: int = 1,
):
    """Decorator to wrap a function with circuit breaker protection.

    Usage:
        @with_circuit_breaker('ollama', failure_threshold=5)
        def my_external_call(ctx):
            # External service call
            pass

    Args:
        service_name: Name of the service for circuit breaker tracking
        failure_threshold: Number of failures before opening
        recovery_timeout: Seconds to wait before trying again
        half_open_max: Max calls allowed in half-open state
    """

    def decorator(func: Callable) -> Callable:
        cb = get_circuit_breaker(
            service_name, failure_threshold, recovery_timeout, half_open_max
        )

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return cb.call(func, *args, **kwargs)
            except CircuitBreakerOpenError as e:
                logger.warning(
                    f"Circuit breaker open for {service_name}, "
                    f"skipping {func.__name__}"
                )
                # Re-raise as SkillExecutionError to maintain contract
                raise SkillExecutionError(
                    func.__name__, original_error=e
                ) from e

        return wrapper

    return decorator


def reset_circuit_breaker(service_name: str) -> None:
    """Reset a circuit breaker to closed state.

    Useful for testing or manual recovery.

    Args:
        service_name: Name of the service to reset
    """
    if service_name in _circuit_breakers:
        _circuit_breakers[service_name].reset()
        logger.info("Reset circuit breaker for %s", service_name)


def get_circuit_breaker_states() -> dict[str, str]:
    """Get current state of all circuit breakers.

    Returns:
        Dict mapping service names to their current state
    """
    return {name: cb.state.value for name, cb in _circuit_breakers.items()}
