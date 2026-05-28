"""Recipe CRUD endpoints.

Extracted from server.py to reduce monolith size.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from uar.api.middleware import security
from uar.services import AuthService, RecipeService

router = APIRouter()

_recipe_svc = RecipeService()
_auth_svc = AuthService()


def _recipe_http_error(
    exc: Exception, recipe_id: str, *, creating: bool = False
) -> HTTPException:
    """Map RecipeService exceptions to HTTP status codes."""
    msg = str(exc)
    if "canonical" in msg.lower():
        return HTTPException(
            status_code=(
                status.HTTP_409_CONFLICT
                if creating
                else status.HTTP_403_FORBIDDEN
            ),
            detail={
                "error": "conflict" if creating else "forbidden",
                "message": (
                    "Recipe already exists"
                    if creating
                    else "Recipe is canonical and cannot be modified"
                ),
            },
        )
    if "skills must be" in msg.lower():
        return HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "invalid_skills",
                "message": "Invalid skills in recipe",
            },
        )
    if isinstance(exc, KeyError):
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "not_found",
                "message": "Recipe not found",
            },
        )
    if isinstance(exc, PermissionError):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error": "forbidden", "message": "Not owner"},
        )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail={"error": "internal", "message": "Internal server error"},
    )


@router.get("/api/uar/recipes")
async def get_recipes(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Return canonical + user-created recipe definitions."""
    user_info = _auth_svc.authenticate(credentials)
    recipes = _recipe_svc.list_all(
        user_id=user_info["user"] if user_info else None
    )
    return {"recipes": recipes}


@router.post("/api/uar/recipes")
async def create_recipe(
    recipe: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Create a new user recipe."""
    user = _auth_svc.require_user(credentials)
    recipe_id = recipe.get("id")
    if not recipe_id or not isinstance(recipe_id, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "missing_id",
                "message": "Recipe must have an 'id' string",
            },
        )
    try:
        _recipe_svc.create(recipe_id, recipe, user["user"])
    except (ValueError, KeyError, PermissionError) as exc:
        raise _recipe_http_error(exc, recipe_id, creating=True) from exc
    return {"created": recipe_id}


@router.put("/api/uar/recipes/{recipe_id}")
async def update_recipe(
    recipe_id: str,
    recipe: dict,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Update an existing user recipe."""
    user = _auth_svc.require_user(credentials)
    try:
        _recipe_svc.update(recipe_id, recipe, user["user"])
    except (ValueError, KeyError, PermissionError) as exc:
        raise _recipe_http_error(exc, recipe_id) from exc
    return {"updated": recipe_id}


@router.delete("/api/uar/recipes/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Delete a user recipe."""
    user = _auth_svc.require_user(credentials)
    try:
        _recipe_svc.delete(recipe_id, user["user"])
    except (ValueError, KeyError, PermissionError) as exc:
        raise _recipe_http_error(exc, recipe_id) from exc
    return {"deleted": recipe_id}
