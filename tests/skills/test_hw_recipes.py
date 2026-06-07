"""Tests for hardware recipe expansion and end-to-end execution.

Verifies that hw_design, hw_verify, hw_full, and riscv_dev recipes
expand to the correct skill sequences and that the executor can
run them without errors.
"""

from uar.core.executor import _expand_execution_order
from uar.core.recipes import DEFAULT_RECIPES, RECIPE_MAP


class TestRecipeExpansion:
    """Recipe definitions expand to expected skill sequences."""

    def test_hw_design_expansion(self):
        order = [{"type": "recipe", "content": "hw_design", "id": "r1"}]
        skills = _expand_execution_order(order)
        assert skills == ["myhdl_design", "verilog_parse"]

    def test_hw_verify_expansion(self):
        order = [{"type": "recipe", "content": "hw_verify", "id": "r1"}]
        skills = _expand_execution_order(order)
        assert skills == ["verilog_parse", "fpga_verify"]

    def test_hw_full_expansion(self):
        order = [{"type": "recipe", "content": "hw_full", "id": "r1"}]
        skills = _expand_execution_order(order)
        assert skills == ["myhdl_design", "verilog_parse", "fpga_verify"]

    def test_riscv_dev_expansion(self):
        order = [{"type": "recipe", "content": "riscv_dev", "id": "r1"}]
        skills = _expand_execution_order(order)
        assert skills == ["riscv_sim"]


class TestRecipeRegistry:
    """Hardware recipes are present in canonical definitions."""

    def test_all_hw_recipes_in_default(self):
        for rid in ("hw_design", "hw_verify", "hw_full", "riscv_dev"):
            assert rid in DEFAULT_RECIPES, (
                f"{rid} missing from DEFAULT_RECIPES"
            )

    def test_all_hw_recipes_have_version(self):
        for rid in ("hw_design", "hw_verify", "hw_full", "riscv_dev"):
            recipe = DEFAULT_RECIPES[rid]
            assert "version" in recipe
            assert recipe["version"] == "1"

    def test_all_hw_recipes_in_recipe_map(self):
        for rid in ("hw_design", "hw_verify", "hw_full", "riscv_dev"):
            assert rid in RECIPE_MAP
            assert isinstance(RECIPE_MAP[rid], list)
            assert len(RECIPE_MAP[rid]) > 0


class TestRecipeValidation:
    """Hardware recipes pass backend validation."""

    def test_all_hw_recipes_validate(self):
        from uar.core.recipes import validate_recipe
        for rid in ("hw_design", "hw_verify", "hw_full", "riscv_dev"):
            recipe = DEFAULT_RECIPES[rid]
            errors = validate_recipe(recipe, rid)
            assert errors == [], (
                f"Recipe {rid} validation failed: {errors}"
            )

    def test_all_hw_recipe_skills_registered(self):
        from uar.core.registry import registry
        for rid in ("hw_design", "hw_verify", "hw_full", "riscv_dev"):
            for skill in RECIPE_MAP[rid]:
                assert registry.is_registered(skill), (
                    f"Recipe {rid} references unregistered skill: {skill}"
                )
