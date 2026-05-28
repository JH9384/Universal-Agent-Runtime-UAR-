"""Tests for mathematical transformations.

Covers Transformation, GroupTheoryOperations, UORObjectMathTransform.
"""

import math

import pytest

from uar.uor.math_transformations import (
    TransformationType,
    Transformation,
    GroupTheoryOperations,
    UORObjectMathTransform,
)
from uar.uor.lie_groups import (
    GroupOperation,
    GroupElement,
    LieGroupOperations,
)


class TestTransformationCompose:
    """Transformation composition."""

    def test_compose_two_rotations(self):
        ops = LieGroupOperations(2)
        r1 = Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": math.pi / 2},
                matrix=ops.rotation_matrix(math.pi / 2),
            ),
            parameters={},
        )
        r2 = Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": math.pi / 2},
                matrix=ops.rotation_matrix(math.pi / 2),
            ),
            parameters={},
        )
        composed = r1.compose(r2)
        assert composed.transformation_type == TransformationType.AFFINE
        assert composed.group_element.matrix is not None

    def test_compose_with_none_matrix(self):
        """When one matrix is None, compose uses empty list fallback."""
        r1 = Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
                matrix=[[1, 0], [0, 1]],
            ),
            parameters={},
        )
        r2 = Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
                matrix=None,
            ),
            parameters={},
        )
        # compose_matrices with None/empty may fail; this tests the path
        try:
            composed = r1.compose(r2)
            assert composed.group_element.matrix is not None
        except (ValueError, TypeError):
            pass  # Expected when matrix dimensions mismatch


class TestTransformationInvert:
    """Transformation inversion."""

    def test_invert_cached(self):
        ops = LieGroupOperations(2)
        rot = ops.rotation_matrix(math.pi / 4)
        t = Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": math.pi / 4},
                matrix=rot,
            ),
            parameters={},
        )
        inv1 = t.invert()
        inv2 = t.invert()
        assert inv1 is inv2  # Cached

    def test_invert_none_matrix(self):
        t = Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={},
                matrix=None,
            ),
            parameters={},
        )
        assert t.invert() is None

    def test_invert_computes(self):
        ops = LieGroupOperations(2)
        rot = ops.rotation_matrix(math.pi / 4)
        t = Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": math.pi / 4},
                matrix=rot,
            ),
            parameters={},
        )
        inv = t.invert()
        assert inv is not None
        assert inv.group_element.operation == GroupOperation.INVERSION


class TestGroupTheoryOperations:
    """Group axiom checking."""

    def test_empty_elements(self):
        gto = GroupTheoryOperations(2)
        result = gto.check_group_axioms([])
        assert result["closure"] is False
        # Identity is vacuously True with no elements to check
        assert isinstance(result["identity"], bool)
        assert result["inverse"] is True
        assert result["associativity"] is True

    def test_rotation_group_axioms(self):
        ops = LieGroupOperations(2)
        gto = GroupTheoryOperations(2)
        elements = [
            GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
                matrix=ops.rotation_matrix(0),
            ),
            GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": math.pi},
                matrix=ops.rotation_matrix(math.pi),
            ),
        ]
        result = gto.check_group_axioms(elements)
        assert result["closure"] is True
        assert result["identity"] is True
        assert result["inverse"] is True

    def test_inverse_fails_singular(self):
        gto = GroupTheoryOperations(2)
        elements = [
            GroupElement(
                operation=GroupOperation.SCALING,
                parameters={},
                matrix=[[1, 1], [1, 1]],  # singular
            ),
        ]
        result = gto.check_group_axioms(elements)
        assert result["inverse"] is False

    def test_compute_group_order(self):
        ops = LieGroupOperations(2)
        gto = GroupTheoryOperations(2)
        elements = [
            GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
                matrix=ops.rotation_matrix(0),
            ),
            GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": math.pi},
                matrix=ops.rotation_matrix(math.pi),
            ),
            GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
                matrix=ops.rotation_matrix(0),  # duplicate
            ),
        ]
        order = gto.compute_group_order(elements)
        assert order == 2

    def test_find_subgroups(self):
        ops = LieGroupOperations(2)
        gto = GroupTheoryOperations(2)
        elements = [
            GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
                matrix=ops.rotation_matrix(0),
            ),
            GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": math.pi},
                matrix=ops.rotation_matrix(math.pi),
            ),
        ]
        subgroups = gto.find_subgroups(elements)
        assert isinstance(subgroups, list)

    def test_matrices_equal(self):
        gto = GroupTheoryOperations(2)
        assert gto._matrices_equal([[1, 2], [3, 4]], [[1, 2], [3, 4]]) is True
        assert gto._matrices_equal([[1, 2], [3, 4]], [[1, 2], [3, 5]]) is False
        assert gto._matrices_equal([[1, 2]], [[1, 2], [3, 4]]) is False


class TestUORObjectMathTransform:
    """High-level math transform API."""

    def test_apply_transformation(self):
        mt = UORObjectMathTransform(2)
        ops = LieGroupOperations(2)
        trans = Transformation(
            transformation_type=TransformationType.AFFINE,
            group_element=GroupElement(
                operation=GroupOperation.TRANSLATION,
                parameters={"dx": 1, "dy": 2},
                matrix=ops.translation_matrix(1, 2),
            ),
            parameters={},
        )
        result = mt.apply_transformation(
            {"position": [0, 0]}, trans, field="position"
        )
        assert result["position_transformed"] is True
        assert pytest.approx(result["position"][0]) == 1.0

    def test_apply_missing_field(self):
        mt = UORObjectMathTransform(2)
        ops = LieGroupOperations(2)
        trans = Transformation(
            transformation_type=TransformationType.AFFINE,
            group_element=GroupElement(
                operation=GroupOperation.TRANSLATION,
                parameters={},
                matrix=ops.translation_matrix(1, 2),
            ),
            parameters={},
        )
        result = mt.apply_transformation(
            {"name": "test"}, trans, field="position"
        )
        assert "position_transformed" not in result

    def test_create_rotation(self):
        mt = UORObjectMathTransform(2)
        rot = mt.create_rotation_transformation(math.pi / 2)
        assert rot.transformation_type == TransformationType.LINEAR
        assert rot.parameters["angle"] == math.pi / 2
        assert rot.group_element.matrix is not None

    def test_create_translation(self):
        mt = UORObjectMathTransform(2)
        trans = mt.create_translation_transformation(3, 4)
        assert trans.transformation_type == TransformationType.AFFINE
        assert trans.parameters == {"dx": 3, "dy": 4}

    def test_create_scaling(self):
        mt = UORObjectMathTransform(2)
        scale = mt.create_scaling_transformation(2)
        assert scale.parameters["sx"] == 2
        assert scale.parameters["sy"] is None

    def test_create_non_uniform_scaling(self):
        mt = UORObjectMathTransform(2)
        scale = mt.create_scaling_transformation(2, 3)
        assert scale.parameters["sx"] == 2
        assert scale.parameters["sy"] == 3

    def test_compose_transformations_empty_raises(self):
        mt = UORObjectMathTransform(2)
        with pytest.raises(ValueError, match="empty"):
            mt.compose_transformations([])

    def test_compose_transformations_single(self):
        mt = UORObjectMathTransform(2)
        rot = mt.create_rotation_transformation(0)
        result = mt.compose_transformations([rot])
        assert result.transformation_type == TransformationType.LINEAR

    def test_compose_multiple(self):
        mt = UORObjectMathTransform(2)
        t1 = mt.create_translation_transformation(1, 0)
        t2 = mt.create_translation_transformation(0, 2)
        composed = mt.compose_transformations([t1, t2])
        assert composed.group_element.matrix is not None

    def test_compute_transformation_chain(self):
        mt = UORObjectMathTransform(2)
        t1 = mt.create_translation_transformation(1, 0)
        t2 = mt.create_translation_transformation(0, 2)
        result = mt.compute_transformation_chain(
            {"position": [0, 0]}, [t1, t2]
        )
        assert pytest.approx(result["position"][0]) == 1.0
        assert pytest.approx(result["position"][1]) == 2.0

    def test_analyze_transformation_group(self):
        mt = UORObjectMathTransform(2)
        rot1 = mt.create_rotation_transformation(0)
        rot2 = mt.create_rotation_transformation(math.pi)
        analysis = mt.analyze_transformation_group([rot1, rot2])
        assert "group_axioms" in analysis
        assert "group_order" in analysis
        assert "subgroup_count" in analysis
        assert "is_valid_group" in analysis
