"""Tests for Lie groups mathematical foundations.

Covers GroupElement, LieGroupOperations, and UORObjectTransformation.
"""

import math
from unittest.mock import patch

import pytest

from uar.uor.lie_groups import (
    GroupOperation,
    GroupElement,
    LieGroupOperations,
    UORObjectTransformation,
)


class TestGroupElement:
    """GroupElement dataclass."""

    def test_to_dict(self):
        elem = GroupElement(
            operation=GroupOperation.ROTATION,
            parameters={"angle": 1.0},
            dimension=2,
            matrix=[[1, 0], [0, 1]],
        )
        d = elem.to_dict()
        assert d["operation"] == "rotation"
        assert d["parameters"] == {"angle": 1.0}
        assert d["dimension"] == 2
        assert d["matrix"] == [[1, 0], [0, 1]]

    def test_defaults(self):
        elem = GroupElement(
            operation=GroupOperation.TRANSLATION,
            parameters={},
        )
        assert elem.dimension == 2
        assert elem.matrix is None


class TestRotationMatrix:
    """2D rotation matrices."""

    def test_identity_rotation(self):
        ops = LieGroupOperations(2)
        m = ops.rotation_matrix(0)
        assert pytest.approx(m[0][0]) == 1.0
        assert pytest.approx(m[0][1]) == 0.0
        assert pytest.approx(m[1][0]) == 0.0
        assert pytest.approx(m[1][1]) == 1.0

    def test_90_degree_rotation(self):
        ops = LieGroupOperations(2)
        m = ops.rotation_matrix(math.pi / 2)
        assert pytest.approx(m[0][0], abs=1e-10) == 0.0
        assert pytest.approx(m[0][1]) == -1.0
        assert pytest.approx(m[1][0]) == 1.0
        assert pytest.approx(m[1][1], abs=1e-10) == 0.0

    def test_numpy_path(self):
        """Test numpy-based computation when available."""
        ops = LieGroupOperations(2)
        m = ops.rotation_matrix(math.pi)
        assert pytest.approx(m[0][0]) == -1.0


class TestTranslationMatrix:
    """Translation matrices."""

    def test_basic(self):
        ops = LieGroupOperations(2)
        m = ops.translation_matrix(3, 4)
        assert m == [[1, 0, 3], [0, 1, 4], [0, 0, 1]]


class TestScalingMatrix:
    """Scaling matrices."""

    def test_uniform(self):
        ops = LieGroupOperations(2)
        m = ops.scaling_matrix(2)
        assert m == [[2, 0, 0], [0, 2, 0], [0, 0, 1]]

    def test_non_uniform(self):
        ops = LieGroupOperations(2)
        m = ops.scaling_matrix(2, 3)
        assert m == [[2, 0, 0], [0, 3, 0], [0, 0, 1]]


class TestReflectionMatrix:
    """Reflection matrices."""

    def test_x_axis(self):
        ops = LieGroupOperations(2)
        m = ops.reflection_matrix("x")
        assert m == [[1, 0, 0], [0, -1, 0], [0, 0, 1]]

    def test_y_axis(self):
        ops = LieGroupOperations(2)
        m = ops.reflection_matrix("y")
        assert m == [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]

    def test_invalid_axis_raises(self):
        ops = LieGroupOperations(2)
        with pytest.raises(ValueError, match="Invalid axis"):
            ops.reflection_matrix("z")


class TestComposeMatrices:
    """Matrix composition."""

    def test_identity_composition(self):
        ops = LieGroupOperations(2)
        ident = [[1, 0], [0, 1]]
        result = ops.compose_matrices(ident, ident)
        assert pytest.approx(result[0][0]) == 1.0
        assert pytest.approx(result[1][1]) == 1.0

    def test_rotation_composition(self):
        ops = LieGroupOperations(2)
        r90 = ops.rotation_matrix(math.pi / 2)
        r180 = ops.rotation_matrix(math.pi)
        composed = ops.compose_matrices(r90, r90)
        # r90 * r90 ≈ r180
        assert pytest.approx(composed[0][0], abs=0.01) == r180[0][0]

    def test_dimension_mismatch_raises(self):
        ops = LieGroupOperations(2)
        m1 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        m2 = [[1, 0], [0, 1]]
        with pytest.raises(
            (ValueError, Exception),
            match="incompatible|mismatch|not aligned",
        ):
            ops.compose_matrices(m1, m2)

    def test_manual_path_no_numpy(self):
        """Test manual matrix multiplication when numpy unavailable."""
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(2)
            m1 = [[1, 2], [3, 4]]
            m2 = [[5, 6], [7, 8]]
            result = ops.compose_matrices(m1, m2)
            assert pytest.approx(result[0][0]) == 19.0
            assert pytest.approx(result[0][1]) == 22.0
            assert pytest.approx(result[1][0]) == 43.0
            assert pytest.approx(result[1][1]) == 50.0


class TestInvertMatrix:
    """Matrix inversion."""

    def test_identity_invert(self):
        ops = LieGroupOperations(2)
        ident = [[1, 0], [0, 1]]
        inv = ops.invert_matrix(ident)
        assert pytest.approx(inv[0][0]) == 1.0
        assert pytest.approx(inv[1][1]) == 1.0

    def test_rotation_invert(self):
        ops = LieGroupOperations(2)
        r = ops.rotation_matrix(math.pi / 4)
        inv = ops.invert_matrix(r)
        # R^T should equal R^-1 for rotation matrices
        composed = ops.compose_matrices(r, inv)
        assert pytest.approx(composed[0][0], abs=0.01) == 1.0
        assert pytest.approx(composed[1][1], abs=0.01) == 1.0

    def test_singular_raises(self):
        ops = LieGroupOperations(2)
        singular = [[1, 1], [1, 1]]
        with pytest.raises(
            (ValueError, Exception), match="singular|Singular"
        ):
            ops.invert_matrix(singular)

    def test_manual_2x2_no_numpy(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(2)
            m = [[4, 7], [2, 6]]
            inv = ops.invert_matrix(m)
            det = 4 * 6 - 7 * 2
            assert pytest.approx(inv[0][0]) == 6 / det
            assert pytest.approx(inv[0][1]) == -7 / det
            assert pytest.approx(inv[1][0]) == -2 / det
            assert pytest.approx(inv[1][1]) == 4 / det

    def test_large_matrix_no_numpy_raises(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(2)
            m3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            with pytest.raises(NotImplementedError):
                ops.invert_matrix(m3)


class TestApplyTransformation:
    """Apply transformations to points."""

    def test_translation_point(self):
        ops = LieGroupOperations(2)
        elem = GroupElement(
            operation=GroupOperation.TRANSLATION,
            parameters={"dx": 3, "dy": 4},
            matrix=ops.translation_matrix(3, 4),
        )
        result = ops.apply_transformation([1, 1], elem)
        assert pytest.approx(result[0]) == 4.0
        assert pytest.approx(result[1]) == 5.0

    def test_generate_matrix_from_params(self):
        """Matrix generated on-the-fly from parameters."""
        ops = LieGroupOperations(2)
        elem = GroupElement(
            operation=GroupOperation.ROTATION,
            parameters={"angle": 0},
        )
        # rotation generates 2x2 but apply adds homogeneous coord
        # Use translation which generates 3x3
        elem = GroupElement(
            operation=GroupOperation.TRANSLATION,
            parameters={"dx": 0, "dy": 0},
        )
        result = ops.apply_transformation([1, 0], elem)
        assert pytest.approx(result[0]) == 1.0
        assert pytest.approx(result[1]) == 0.0

    def test_reflection_point(self):
        ops = LieGroupOperations(2)
        elem = GroupElement(
            operation=GroupOperation.REFLECTION,
            parameters={"axis": "x"},
        )
        result = ops.apply_transformation([1, 2], elem)
        assert pytest.approx(result[0]) == 1.0
        assert pytest.approx(result[1]) == -2.0

    def test_unsupported_operation_raises(self):
        ops = LieGroupOperations(2)
        elem = GroupElement(
            operation=GroupOperation.COMPOSITION,
            parameters={},
        )
        with pytest.raises(ValueError, match="Unsupported"):
            ops.apply_transformation([1, 0], elem)

    def test_2x2_matrix_no_numpy(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(2)
            elem = GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
                matrix=[[1, 0], [0, 1]],
            )
            result = ops.apply_transformation([1, 2], elem)
            assert pytest.approx(result[0]) == 1.0
            assert pytest.approx(result[1]) == 2.0


class TestCreateGroupElement:
    """Group element factory."""

    def test_basic(self):
        ops = LieGroupOperations(3)
        elem = ops.create_group_element(
            GroupOperation.SCALING,
            {"sx": 2},
        )
        assert elem.operation == GroupOperation.SCALING
        assert elem.dimension == 3
        assert elem.matrix is None


class TestLieAlgebraBasis:
    """Lie algebra basis elements."""

    def test_se2_basis(self):
        ops = LieGroupOperations(2)
        basis = ops.get_lie_algebra_basis()
        assert "translation_x" in basis
        assert "translation_y" in basis
        assert "rotation" in basis
        assert len(basis["rotation"]) == 3


class TestExponentialMap:
    """Exponential map from algebra to group."""

    def test_zero_element(self):
        ops = LieGroupOperations(2)
        zero = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        result = ops.exponential_map(zero)
        # exp(0) = I
        assert pytest.approx(result[0][0], abs=0.01) == 1.0
        assert pytest.approx(result[1][1], abs=0.01) == 1.0
        assert pytest.approx(result[2][2], abs=0.01) == 1.0

    def test_no_numpy_raises(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(2)
            with pytest.raises(NotImplementedError):
                ops.exponential_map([[0, 0], [0, 0]])


class TestUORObjectTransformation:
    """High-level object transformation API."""

    def test_transform_object_position(self):
        transformer = UORObjectTransformation(2)
        trans = GroupElement(
            operation=GroupOperation.TRANSLATION,
            parameters={"dx": 1, "dy": 2},
            matrix=[[1, 0, 1], [0, 1, 2], [0, 0, 1]],
        )
        result = transformer.transform_object_position([0, 0], [trans])
        assert pytest.approx(result[0]) == 1.0
        assert pytest.approx(result[1]) == 2.0

    def test_compose_transformations(self):
        transformer = UORObjectTransformation(2)
        t1 = GroupElement(
            operation=GroupOperation.TRANSLATION,
            parameters={"dx": 1, "dy": 0},
            matrix=[[1, 0, 1], [0, 1, 0], [0, 0, 1]],
        )
        t2 = GroupElement(
            operation=GroupOperation.TRANSLATION,
            parameters={"dx": 0, "dy": 2},
            matrix=[[1, 0, 0], [0, 1, 2], [0, 0, 1]],
        )
        composed = transformer.compose_transformations([t1, t2])
        assert composed.operation == GroupOperation.COMPOSITION
        assert composed.parameters["composed_count"] == 2
        assert composed.matrix is not None

    def test_compose_empty_raises(self):
        transformer = UORObjectTransformation(2)
        with pytest.raises(ValueError, match="empty"):
            transformer.compose_transformations([])

    def test_compose_from_params(self):
        """Compose when matrices need to be generated from parameters."""
        transformer = UORObjectTransformation(2)
        t1 = GroupElement(
            operation=GroupOperation.ROTATION,
            parameters={"angle": 0},
        )
        composed = transformer.compose_transformations([t1])
        assert composed.matrix is not None
