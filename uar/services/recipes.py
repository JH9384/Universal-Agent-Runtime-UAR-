"""Recipe CRUD service — centralises all recipe business logic.

Eliminates duplication across GET / POST / PUT / DELETE endpoints
in ``server.py`` where auth checks, canonical guards, and owner
verification were repeated identically.
"""

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from uar.core.recipes import DEFAULT_RECIPES
from .base import BaseService


class RecipeService(BaseService):
    """Handles canonical + user-created recipes with persistence."""

    def __init__(
        self,
        path: Optional[Path] = None,
        **deps: Any,
    ) -> None:
        super().__init__(**deps)
        self._path = path or self._default_recipes_path()
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _default_recipes_path() -> Path:
        root = Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
        p = root / ".uar_data" / "user_recipes.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    def load(
        self, user_id: Optional[str] = None
    ) -> dict[str, dict[str, Any]]:
        if not self._path.exists():
            return {}
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                self._log(
                    "warning",
                    f"Corrupted recipe file {self._path}; expected dict, "
                    f"got {type(data).__name__}. Returning empty.",
                )
                return {}
            if user_id is None:
                return data
            return {
                k: v
                for k, v in data.items()
                if v.get("user_id") == user_id or v.get("user_id") is None
            }
        except json.JSONDecodeError as exc:
            self._log(
                "error",
                f"Invalid JSON in recipe file {self._path}: {exc}. "
                f"Returning empty.",
            )
            return {}
        except OSError as exc:
            self._log(
                "error",
                f"Cannot read recipe file {self._path}: {exc}. "
                f"Returning empty.",
            )
            return {}

    def save(self, recipes: dict[str, dict[str, Any]]) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(recipes, f, indent=2)

    @staticmethod
    def _validate_skills(data: dict[str, Any]) -> None:
        skills = data.get("skills")
        if not isinstance(skills, list) or not all(
            isinstance(s, str) for s in skills
        ):
            raise ValueError("skills must be a list of strings")

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------
    def list_all(
        self, user_id: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """Return merged canonical + user recipes."""
        user_recipes = self.load(user_id)
        recipes: list[dict[str, Any]] = []
        seen: set[str] = set()
        for rid, r in DEFAULT_RECIPES.items():
            recipes.append(
                {
                    "id": rid,
                    "label": r.get("label", rid),
                    "skills": r.get("skills", []),
                    "hint": r.get("hint", ""),
                }
            )
            seen.add(rid)
        if user_id:
            for rid, r in user_recipes.items():
                if rid not in seen:
                    recipes.append(
                        {
                            "id": rid,
                            "label": r.get("label", rid),
                            "skills": r.get("skills", []),
                            "hint": r.get("hint", ""),
                        }
                    )
        return recipes

    def get_user(self, recipe_id: str) -> Optional[dict[str, Any]]:
        return self.load().get(recipe_id)

    # ------------------------------------------------------------------
    # Write operations
    # ------------------------------------------------------------------
    def create(
        self, recipe_id: str, data: dict[str, Any], user_id: str
    ) -> str:
        if recipe_id in DEFAULT_RECIPES:
            raise ValueError(f"Recipe '{recipe_id}' is canonical")
        self._validate_skills(data)
        data["user_id"] = user_id
        with self._lock:
            recipes = self.load()
            recipes[recipe_id] = data
            self.save(recipes)
        return recipe_id

    def update(
        self, recipe_id: str, data: dict[str, Any], user_id: str
    ) -> str:
        if recipe_id in DEFAULT_RECIPES:
            raise ValueError(f"Recipe '{recipe_id}' is canonical")
        self._validate_skills(data)
        data["id"] = recipe_id
        with self._lock:
            recipes = self.load()
            existing = recipes.get(recipe_id)
            if not existing:
                raise KeyError(f"Recipe '{recipe_id}' not found")
            owner = existing.get("user_id")
            if owner and owner != user_id:
                raise PermissionError("Not owner")
            data["user_id"] = user_id
            recipes[recipe_id] = data
            self.save(recipes)
        return recipe_id

    def delete(self, recipe_id: str, user_id: str) -> str:
        if recipe_id in DEFAULT_RECIPES:
            raise ValueError(f"Recipe '{recipe_id}' is canonical")
        with self._lock:
            recipes = self.load()
            existing = recipes.get(recipe_id)
            if not existing:
                raise KeyError(f"Recipe '{recipe_id}' not found")
            owner = existing.get("user_id")
            if owner and owner != user_id:
                raise PermissionError("Not owner")
            del recipes[recipe_id]
            self.save(recipes)
        return recipe_id
