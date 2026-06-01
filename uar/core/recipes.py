"""Shared recipe definitions for UAR.

This module contains the canonical recipe definitions used by both
the executor and the API server to avoid duplication.
"""

import json
import logging
import os
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Current schema version for recipes.
# Bump this when the recipe structure changes in a backward-incompatible way.
CURRENT_RECIPE_VERSION = "1"

# Recipe definitions matching frontend RECIPES
# All canonical recipes include a 'version' field for schema tracking.
DEFAULT_RECIPES: Dict[str, Dict[str, Any]] = {
    "review": {
        "id": "review",
        "version": "1",
        "label": "🦙 Ollama review",
        "skills": ["doc_ingest", "ollama_generate"],
        "hint": "Quick LLM review of library docs",
    },
    "deps": {
        "id": "deps",
        "version": "1",
        "label": "🕸️ Dep map",
        "skills": ["doc_ingest", "dependency_map", "sum_review"],
        "hint": "Build a dependency graph",
    },
    "gr_index": {
        "id": "gr_index",
        "version": "1",
        "label": "📚 GraphRAG index",
        "skills": ["graphrag_index"],
        "hint": "Build the knowledge graph (slow, one-time)",
    },
    "gr_query": {
        "id": "gr_query",
        "version": "1",
        "label": "🔎 GraphRAG query",
        "skills": ["graphrag_query"],
        "hint": "Query an existing graph",
    },
    "gr_full": {
        "id": "gr_full",
        "version": "1",
        "label": "⚡ Full pipeline",
        "skills": ["graphrag_index", "graphrag_query"],
        "hint": "Index then query (very slow)",
    },
    "auto_up": {
        "id": "auto_up",
        "version": "1",
        "label": "☁️ Autonomi upload",
        "skills": ["autonomi_upload"],
        "hint": "Upload current input_path to Autonomi",
    },
    "auto_down": {
        "id": "auto_down",
        "version": "1",
        "label": "☁️ Autonomi download",
        "skills": ["autonomi_download"],
        "hint": "Download from Autonomi address",
    },
    "auto_status": {
        "id": "auto_status",
        "version": "1",
        "label": "☁️ Autonomi status",
        "skills": ["autonomi_status"],
        "hint": "Check Autonomi connectivity",
    },
    "eco_status": {
        "id": "eco_status",
        "version": "1",
        "label": "🌐 Ecosystem status",
        "skills": ["uor_ecosystem_status"],
        "hint": "Check all UOR ecosystem integrations",
    },
    "eco_canon": {
        "id": "eco_canon",
        "version": "1",
        "label": "🌐 Canonicalize",
        "skills": ["uor_addr_canonicalize"],
        "hint": "Canonicalize data per UOR-ADDR-1",
    },
    "eco_foundation": {
        "id": "eco_foundation",
        "version": "1",
        "label": "🌐 Foundation verify",
        "skills": ["uor_foundation_verify"],
        "hint": "Call the live UOR Foundation API",
    },
}

# Create RECIPE_MAP for quick lookup of skill lists by recipe ID
RECIPE_MAP: Dict[str, List[str]] = {
    recipe_id: recipe["skills"]
    for recipe_id, recipe in DEFAULT_RECIPES.items()
    if "skills" in recipe
}


def _get_user_recipes_path() -> Path:
    """Return the canonical path to user_recipes.json."""
    root = Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
    return root / ".uar_data" / "user_recipes.json"


def _load_user_recipes() -> Dict[str, Dict[str, Any]]:
    """Load user-created recipes from disk."""
    p = _get_user_recipes_path()
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError) as exc:
        logger.warning("Failed to load user recipes from %s: %s", p, exc)
    return {}


_user_recipes_cache: Optional[Dict[str, Dict[str, Any]]] = None
_user_recipes_cache_mtime_ns: Optional[int] = None
_user_recipes_cache_lock = threading.Lock()


def _recipes_file_mtime_ns() -> Optional[int]:
    """Return file mtime in nanoseconds for sub-second precision."""
    p = _get_user_recipes_path()
    try:
        return os.stat(p).st_mtime_ns
    except OSError:
        return None


def get_recipe_skills(recipe_id: str) -> Optional[List[str]]:
    """Return skill list for a recipe, checking canonical then user recipes."""
    canonical = RECIPE_MAP.get(recipe_id)
    if canonical is not None:
        return canonical
    global _user_recipes_cache, _user_recipes_cache_mtime_ns
    with _user_recipes_cache_lock:
        current_mtime = _recipes_file_mtime_ns()
        cache_stale = (
            _user_recipes_cache is None
            or (current_mtime is None
                and _user_recipes_cache_mtime_ns is not None)
            # File existed before but is gone now
            or (current_mtime is not None
                and _user_recipes_cache_mtime_ns is None)
            # File didn't exist before but exists now
            or (current_mtime is not None
                and _user_recipes_cache_mtime_ns is not None
                and current_mtime != _user_recipes_cache_mtime_ns)
            # File changed since last load (nanosecond precision)
        )
        if cache_stale:
            _user_recipes_cache = _load_user_recipes()
            _user_recipes_cache_mtime_ns = current_mtime
        recipe = _user_recipes_cache.get(recipe_id)
        if recipe:
            skills = recipe.get("skills")
            if isinstance(skills, list):
                return skills
        return None


def clear_recipes_cache() -> None:
    """Clear the in-memory user recipes cache.

    Call after modifying the user recipes file on disk to force a
    reload on the next ``get_recipe_skills`` call.
    """
    global _user_recipes_cache, _user_recipes_cache_mtime_ns
    with _user_recipes_cache_lock:
        _user_recipes_cache = None
        _user_recipes_cache_mtime_ns = None


def validate_recipe(recipe: Dict[str, Any], recipe_id: str = "") -> List[str]:
    """Validate a single recipe against the current schema.

    Returns a list of validation error messages. An empty list means
    the recipe is valid.
    """
    errors: List[str] = []

    # Required fields
    if not isinstance(recipe.get("id"), str) or not recipe.get("id"):
        errors.append("Recipe missing or invalid 'id' field")

    if not isinstance(recipe.get("label"), str) or not recipe.get("label"):
        errors.append("Recipe missing or invalid 'label' field")

    skills = recipe.get("skills")
    if not isinstance(skills, list):
        errors.append("Recipe 'skills' must be a list")
    else:
        for _, skill in enumerate(skills):
            if isinstance(skill, list):
                # Parallel group
                for _, sub in enumerate(skill):
                    if not isinstance(sub, str) or not sub:
                        errors.append(
                            "Recipe skill must be a non-empty string"
                        )
            elif not isinstance(skill, str) or not skill:
                errors.append(
                    "Recipe skill must be a non-empty string"
                )

    # Optional fields with type checks
    hint = recipe.get("hint")
    if hint is not None and not isinstance(hint, str):
        errors.append("Recipe 'hint' must be a string")

    condition = recipe.get("condition")
    if condition is not None and not isinstance(condition, dict):
        errors.append("Recipe 'condition' must be a dict")

    version = recipe.get("version")
    if version is not None and not isinstance(version, str):
        errors.append("Recipe 'version' must be a string")

    return errors


def migrate_recipe(recipe: Dict[str, Any]) -> Dict[str, Any]:
    """Migrate a recipe to the current schema version.

    Currently only version "1" exists, so this is a no-op for
    well-formed v1 recipes. Future versions can add normalization
    logic here (e.g., renaming fields, adding defaults).
    """
    version = recipe.get("version", "1")

    if version == "1":
        # Ensure all v1 recipes have a version field
        if "version" not in recipe:
            recipe = dict(recipe)
            recipe["version"] = "1"
        return recipe

    # Unknown version: return as-is but log a warning.
    # The caller should decide whether to reject or accept.
    logger.warning(
        "Recipe '%s' has unknown version '%s'. "
        "Passing through without migration.",
        recipe.get('id', '<unknown>'),
        version,
    )
    return recipe


def validate_recipes() -> None:
    """Validate that all skills in recipes are registered.

    This function is called at module load time to catch invalid
    skill references early rather than at runtime.
    """
    try:
        from .registry import registry

        all_valid = True
        for recipe_id, recipe in DEFAULT_RECIPES.items():
            # Schema validation
            schema_errors = validate_recipe(recipe, recipe_id)
            if schema_errors:
                for err in schema_errors:
                    logger.warning(err)
                all_valid = False

            # Skill registry validation
            skills = recipe.get("skills", [])
            for skill in skills:
                if isinstance(skill, list):
                    for sub in skill:
                        if not registry.is_registered(sub):
                            logger.warning(
                                "Recipe '%s' references "
                                "unregistered skill: %s",
                                recipe_id,
                                sub,
                            )
                            all_valid = False
                elif not registry.is_registered(skill):
                    logger.warning(
                        "Recipe '%s' references "
                        "unregistered skill: %s",
                        recipe_id,
                        skill,
                    )
                    all_valid = False

        if all_valid:
            logger.info("All recipe skills validated successfully")
    except ImportError:
        # Registry might not be available during import
        logger.warning(
            "Could not validate recipes against registry - "
            "registry not available"
        )


# Note: validate_recipes() is called explicitly from server.py after all
# skills are imported, to avoid false "unregistered skill" warnings during
# the import-order window when recipes are loaded before skills.
