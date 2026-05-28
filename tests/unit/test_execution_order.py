"""Tests for ``_expand_execution_order_with_markers`` and the
``orchestration_plan`` event payload.

These pin the contract used by the frontend (UARPanel) to render recipe
boundaries in the unified-order view.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from uar.core.exceptions import ValidationError
from uar.core.executor import (
    _expand_execution_order,
    _expand_execution_order_with_markers,
)
from uar.core.recipes import DEFAULT_RECIPES


def _flat_skill(content: str, instance_id: str = "") -> Dict[str, Any]:
    return {"id": instance_id, "type": "skill", "content": content}


def _flat_recipe(content: str, instance_id: str = "") -> Dict[str, Any]:
    return {"id": instance_id, "type": "recipe", "content": content}


def test_skills_only_yields_no_markers():
    order = [_flat_skill("doc_ingest"), _flat_skill("dependency_map")]
    skills, markers = _expand_execution_order_with_markers(order)
    assert skills == ["doc_ingest", "dependency_map"]
    assert markers == []


def test_single_recipe_emits_start_and_end_markers():
    # Pick any default recipe with a known skill list
    recipe_id, recipe = next(iter(DEFAULT_RECIPES.items()))
    expected_skills: List[str] = list(recipe["skills"])

    order = [_flat_recipe(recipe_id, instance_id="r1")]
    skills, markers = _expand_execution_order_with_markers(order)

    assert skills == expected_skills
    assert len(markers) == 2
    start, end = markers
    assert start["kind"] == "start"
    assert start["index"] == 0
    assert start["recipe_id"] == recipe_id
    assert start["instance_id"] == "r1"
    assert end["kind"] == "end"
    assert end["index"] == len(expected_skills)
    assert end["recipe_id"] == recipe_id
    assert end["instance_id"] == "r1"


def test_recipe_followed_by_skill_has_correct_indices():
    recipe_id, recipe = next(iter(DEFAULT_RECIPES.items()))
    recipe_len = len(recipe["skills"])

    order = [
        _flat_recipe(recipe_id, instance_id="r1"),
        _flat_skill("sum_review", instance_id="s1"),
    ]
    skills, markers = _expand_execution_order_with_markers(order)

    assert skills == [*recipe["skills"], "sum_review"]
    starts = [m for m in markers if m["kind"] == "start"]
    ends = [m for m in markers if m["kind"] == "end"]
    assert len(starts) == 1 and len(ends) == 1
    assert starts[0]["index"] == 0
    assert ends[0]["index"] == recipe_len


def test_two_recipes_back_to_back_have_independent_instance_ids():
    recipe_id, recipe = next(iter(DEFAULT_RECIPES.items()))
    recipe_len = len(recipe["skills"])

    order = [
        _flat_recipe(recipe_id, instance_id="a"),
        _flat_recipe(recipe_id, instance_id="b"),
    ]
    skills, markers = _expand_execution_order_with_markers(order)

    assert skills == [*recipe["skills"], *recipe["skills"]]
    assert [m["instance_id"] for m in markers] == ["a", "a", "b", "b"]
    assert [m["index"] for m in markers] == [
        0,
        recipe_len,
        recipe_len,
        recipe_len * 2,
    ]


def test_unknown_recipe_raises_validation_error():
    with pytest.raises(ValidationError):
        _expand_execution_order_with_markers([_flat_recipe("ghost-recipe")])


def test_legacy_expand_returns_only_skills():
    recipe_id, _ = next(iter(DEFAULT_RECIPES.items()))
    order = [_flat_recipe(recipe_id), _flat_skill("sum_review")]
    flat = _expand_execution_order(order)
    expanded, _ = _expand_execution_order_with_markers(order)
    assert flat == expanded


def test_invalid_item_type_is_skipped_with_warning(caplog):
    skills, markers = _expand_execution_order_with_markers(
        [{"id": "x", "type": "ghost", "content": "irrelevant"}]
    )
    assert skills == []
    assert markers == []
