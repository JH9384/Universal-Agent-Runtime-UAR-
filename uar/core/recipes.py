"""Shared recipe definitions for UAR.

This module contains the canonical recipe definitions used by both
the executor and the API server to avoid duplication.
"""

import json
import logging
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


def _load_user_recipes() -> Dict[str, Dict[str, Any]]:
    """Load user-created recipes from disk."""
    import os
    from pathlib import Path

    root = Path(os.getenv("PROJECT_ROOT", Path.cwd())).resolve()
    p = root / ".uar_data" / "user_recipes.json"
    if not p.exists():
        return {}
    try:
        with open(p, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, OSError):
        pass
    return {}


def get_recipe_skills(recipe_id: str) -> Optional[List[str]]:
    """Return skill list for a recipe, checking canonical then user recipes."""
    canonical = RECIPE_MAP.get(recipe_id)
    if canonical is not None:
        return canonical
    user_recipes = _load_user_recipes()
    recipe = user_recipes.get(recipe_id)
    if recipe:
        skills = recipe.get("skills")
        if isinstance(skills, list):
            return skills
    return None


def validate_recipe(recipe: Dict[str, Any], recipe_id: str = "") -> List[str]:
    """Validate a single recipe against the current schema.

    Returns a list of validation error messages. An empty list means
    the recipe is valid.
    """
    errors: List[str] = []
    rid = recipe_id or recipe.get("id", "<unknown>")

    # Required fields
    if not isinstance(recipe.get("id"), str) or not recipe.get("id"):
        errors.append(f"Recipe {rid}: missing or invalid 'id' field")

    if not isinstance(recipe.get("label"), str) or not recipe.get("label"):
        errors.append(f"Recipe {rid}: missing or invalid 'label' field")

    skills = recipe.get("skills")
    if not isinstance(skills, list):
        errors.append(f"Recipe {rid}: 'skills' must be a list")
    else:
        for i, skill in enumerate(skills):
            if isinstance(skill, list):
                # Parallel group
                for j, sub in enumerate(skill):
                    if not isinstance(sub, str) or not sub:
                        errors.append(
                            f"Recipe {rid}: skill group[{i}][{j}] must be a "
                            f"non-empty string"
                        )
            elif not isinstance(skill, str) or not skill:
                errors.append(
                    f"Recipe {rid}: skills[{i}] must be a non-empty string"
                )

    # Optional fields with type checks
    hint = recipe.get("hint")
    if hint is not None and not isinstance(hint, str):
        errors.append(f"Recipe {rid}: 'hint' must be a string")

    condition = recipe.get("condition")
    if condition is not None and not isinstance(condition, dict):
        errors.append(f"Recipe {rid}: 'condition' must be a dict")

    version = recipe.get("version")
    if version is not None and not isinstance(version, str):
        errors.append(f"Recipe {rid}: 'version' must be a string")

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
        f"Recipe '{recipe.get('id', '<unknown>')}' has unknown version "
        f"'{version}'. Passing through without migration."
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
                                f"Recipe '{recipe_id}' references "
                                f"unregistered skill: {sub}"
                            )
                            all_valid = False
                elif not registry.is_registered(skill):
                    logger.warning(
                        f"Recipe '{recipe_id}' references unregistered "
                        f"skill: {skill}"
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
