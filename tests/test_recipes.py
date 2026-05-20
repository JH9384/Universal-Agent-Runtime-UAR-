"""Tests for recipe schema validation and migration."""

from uar.core.recipes import (
    CURRENT_RECIPE_VERSION,
    DEFAULT_RECIPES,
    migrate_recipe,
    validate_recipe,
)


def test_current_version_is_string():
    assert isinstance(CURRENT_RECIPE_VERSION, str)
    assert CURRENT_RECIPE_VERSION == "1"


def test_all_canonical_recipes_have_version():
    for recipe_id, recipe in DEFAULT_RECIPES.items():
        assert "version" in recipe, f"Recipe '{recipe_id}' missing 'version'"
        assert recipe["version"] == "1"


def test_validate_recipe_valid():
    recipe = {
        "id": "test",
        "version": "1",
        "label": "Test recipe",
        "skills": ["doc_ingest", "ollama_generate"],
        "hint": "A test",
    }
    errors = validate_recipe(recipe)
    assert errors == []


def test_validate_recipe_missing_id():
    recipe = {"label": "Test", "skills": ["doc_ingest"]}
    errors = validate_recipe(recipe)
    assert any("missing or invalid 'id'" in e for e in errors)


def test_validate_recipe_missing_label():
    recipe = {"id": "test", "skills": ["doc_ingest"]}
    errors = validate_recipe(recipe)
    assert any("missing or invalid 'label'" in e for e in errors)


def test_validate_recipe_skills_not_list():
    recipe = {"id": "test", "label": "Test", "skills": "doc_ingest"}
    errors = validate_recipe(recipe)
    assert any("'skills' must be a list" in e for e in errors)


def test_validate_recipe_skill_not_string():
    recipe = {"id": "test", "label": "Test", "skills": [123]}
    errors = validate_recipe(recipe)
    assert any("must be a non-empty string" in e for e in errors)


def test_validate_recipe_parallel_group():
    recipe = {
        "id": "test",
        "label": "Test",
        "skills": [["doc_ingest", "dependency_map"]],
    }
    errors = validate_recipe(recipe)
    assert errors == []


def test_validate_recipe_parallel_group_invalid():
    recipe = {
        "id": "test",
        "label": "Test",
        "skills": [["doc_ingest", 123]],
    }
    errors = validate_recipe(recipe)
    assert any(
        "skill group" in e and "must be a non-empty string" in e
        for e in errors
    )


def test_validate_recipe_optional_fields():
    recipe = {
        "id": "test",
        "label": "Test",
        "skills": ["doc_ingest"],
        "hint": 123,
        "condition": "bad",
        "version": 1,
    }
    errors = validate_recipe(recipe)
    assert any("'hint' must be a string" in e for e in errors)
    assert any("'condition' must be a dict" in e for e in errors)
    assert any("'version' must be a string" in e for e in errors)


def test_migrate_recipe_v1_no_version():
    recipe = {"id": "test", "label": "Test", "skills": ["doc_ingest"]}
    migrated = migrate_recipe(recipe)
    assert migrated["version"] == "1"
    assert migrated["id"] == "test"


def test_migrate_recipe_v1_with_version():
    recipe = {"id": "test", "version": "1", "skills": ["doc_ingest"]}
    migrated = migrate_recipe(recipe)
    assert migrated["version"] == "1"
    # Should return same dict (not mutated in place)
    assert migrated is recipe


def test_migrate_recipe_unknown_version():
    recipe = {"id": "test", "version": "99", "skills": ["doc_ingest"]}
    migrated = migrate_recipe(recipe)
    # Unknown versions pass through with a warning
    assert migrated["version"] == "99"


def test_validate_recipe_uses_recipe_id_param():
    recipe = {"id": "", "label": "", "skills": []}
    errors = validate_recipe(recipe, recipe_id="fallback")
    assert any("Recipe fallback" in e for e in errors)
