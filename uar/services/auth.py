"""Authentication and authorization service.

Eliminates duplicated auth-check boilerplate across endpoints:
- Recipe CRUD endpoints all had
  ``if not user_info: raise HTTPException(401, ...)``
- WebSocket handlers had inline auth parsing + validation
"""

from typing import Any, Optional
from fastapi import HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials
from .base import BaseService


class AuthService(BaseService):
    """Centralised auth checks with reusable helpers.

    Usage in routers::

        auth = AuthService()
        user = auth.require_user(credentials)  # raises 401 if anon
        auth.require_owner(recipe, user)     # raises 403 if not owner
    """

    def authenticate(
        self, credentials: Optional[HTTPAuthorizationCredentials]
    ) -> Optional[dict[str, Any]]:
        """Authenticate and return user info dict, or None for anonymous."""
        from uar.api.middleware import auth_middleware

        return auth_middleware(credentials)

    def require_user(
        self, credentials: Optional[HTTPAuthorizationCredentials]
    ) -> dict[str, Any]:
        """Require authenticated user; raise 401 if anonymous."""
        user = self.authenticate(credentials)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error": "unauthorized",
                    "message": "Authentication required",
                },
            )
        return user

    def require_owner(
        self,
        resource: dict[str, Any],
        user: dict[str, Any],
        field: str = "user_id",
    ) -> None:
        """Raise 403 if user does not own the resource."""
        owner = resource.get(field)
        if owner and owner != user["user"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": "Not owner of this resource",
                },
            )

    def forbid_canonical(
        self, recipe_id: str, canon: set[str], action: str = "modify"
    ) -> None:
        """Raise 403 if recipe_id is in the canonical set."""
        if recipe_id in canon:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "error": "forbidden",
                    "message": (
                        f"Cannot {action} canonical recipe"
                        f" '{recipe_id}'"
                    ),
                },
            )

    @staticmethod
    def parse_websocket_auth(
        headers: dict[str, str], query_params: dict[str, str]
    ) -> Optional[HTTPAuthorizationCredentials]:
        """Extract Bearer token from WebSocket headers or query params."""
        auth_header = headers.get("authorization", "")
        if auth_header.lower().startswith("bearer "):
            return HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=auth_header[7:],
            )
        token = query_params.get("token")
        if token:
            return HTTPAuthorizationCredentials(
                scheme="Bearer",
                credentials=token,
            )
        return None
