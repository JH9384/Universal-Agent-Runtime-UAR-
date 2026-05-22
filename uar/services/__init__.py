"""UAR Service Layer

Encapsulates business logic to eliminate duplication between API routes,
WebSocket handlers, and other entry points. All services are stateless
and accept dependencies via constructor injection for testability.

Usage:
    from uar.services import GoalExecutionService, EventService
    execution = GoalExecutionService(store, event_svc, rate_limit_svc)
    async for event in execution.stream_goal(req, request_id, user):
        ...
"""

from .auth import AuthService
from .events import EventService
from .execution import GoalExecutionService
from .recipes import RecipeService
from .rate_limit import RateLimitService

__all__ = [
    "AuthService",
    "EventService",
    "GoalExecutionService",
    "RecipeService",
    "RateLimitService",
]
