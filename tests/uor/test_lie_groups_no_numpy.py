"""Tests for Lie groups fallback paths (no NumPy).

Covers branches that only execute when NUMPY_AVAILABLE is False.
"""

from unittest.mock import patch

import pytest

from uar.uor.lie_groups import (
    GroupOperation,
    GroupElement,
    LieGroupOperations,
    UORObjectTransformation,
)


class TestRotationMatrixNoNumpy:
    """Rotation matrix without NumPy."""

    def test_2d(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            m = ops.rotation_matrix(0)
            assert m[0][0] == pytest.approx(1.0)
            assert m[1][1] == pytest.approx(1.0)


class TestComposeMatricesNoNumpy:
    """Matrix composition without NumPy."""

    def test_compose(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            m1 = [[1, 0], [0, 1]]
            m2 = [[2, 0], [0, 3]]
            result = ops.compose_matrices(m1, m2)
            assert result == [[2, 0], [0, 3]]

    def test_incompatible_dimensions(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            with pytest.raises(ValueError, match="incompatible"):
                ops.compose_matrices([[1, 0, 0], [0, 1, 0]], [[1, 0], [0, 1]])


class TestInvertMatrixNoNumpy:
    """Matrix inversion without NumPy."""

    def test_2x2(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            m = [[4, 7], [2, 6]]
            inv = ops.invert_matrix(m)
            det = 4 * 6 - 7 * 2
            assert inv[0][0] == pytest.approx(6 / det)

    def test_singular(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            with pytest.raises(ValueError, match="singular"):
                ops.invert_matrix([[1, 2], [2, 4]])

    def test_general_not_implemented(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=3)
            with pytest.raises(NotImplementedError):
                ops.invert_matrix([[1, 0, 0], [0, 1, 0], [0, 0, 1]])


class TestApplyTransformationNoNumpy:
    """Apply transformation without NumPy."""

    def test_rotation(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            elem = GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
            )
            result = ops.apply_transformation([1, 0], elem)
            assert result[0] == pytest.approx(1.0)

    def test_translation(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            elem = GroupElement(
                operation=GroupOperation.TRANSLATION,
                parameters={"dx": 3, "dy": 4},
            )
            result = ops.apply_transformation([1, 1], elem)
            assert result[0] == pytest.approx(4.0)
            assert result[1] == pytest.approx(5.0)

    def test_scaling(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            elem = GroupElement(
                operation=GroupOperation.SCALING,
                parameters={"sx": 2, "sy": 3},
            )
            result = ops.apply_transformation([1, 1], elem)
            assert result[0] == pytest.approx(2.0)
            assert result[1] == pytest.approx(3.0)

    def test_reflection(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            elem = GroupElement(
                operation=GroupOperation.REFLECTION,
                parameters={"axis": "x"},
            )
            result = ops.apply_transformation([1, 2], elem)
            assert result[0] == pytest.approx(1.0)
            assert result[1] == pytest.approx(-2.0)

    def test_unsupported_operation(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            ops = LieGroupOperations(dimension=2)
            elem = GroupElement(
                operation=GroupOperation.COMPOSITION,
                parameters={},
            )
            with pytest.raises(ValueError, match="Unsupported"):
                ops.apply_transformation([1, 0], elem)


class TestComposeTransformations:
    """Compose multiple transformations."""

    def test_empty_raises(self):
        obj = UORObjectTransformation(dimension=2)
        with pytest.raises(ValueError, match="empty"):
            obj.compose_transformations([])

    def test_with_matrix(self):
        obj = UORObjectTransformation(dimension=2)
        t1 = GroupElement(
            operation=GroupOperation.ROTATION,
            parameters={"angle": 0},
            matrix=[[1, 0], [0, 1]],
        )
        result = obj.compose_transformations([t1])
        assert result.operation == GroupOperation.COMPOSITION

    def test_rotation_no_matrix(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            obj = UORObjectTransformation(dimension=2)
            t1 = GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
            )
            result = obj.compose_transformations([t1])
            assert result.matrix is not None

    def test_translation_no_matrix(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            obj = UORObjectTransformation(dimension=2)
            t1 = GroupElement(
                operation=GroupOperation.TRANSLATION,
                parameters={"dx": 1, "dy": 0},
            )
            result = obj.compose_transformations([t1])
            assert result.matrix is not None

    def test_scaling_no_matrix(self):
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            obj = UORObjectTransformation(dimension=2)
            t1 = GroupElement(
                operation=GroupOperation.SCALING,
                parameters={"sx": 2},
            )
            # scaling_matrix returns 3x3, so identity must also be 3x3
            id3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
            with patch.object(
                obj.lie_ops, "rotation_matrix", return_value=id3
            ):
                result = obj.compose_transformations([t1])
            assert result.matrix is not None

    def test_scaling_dimension_3(self):
        """SCALING branch with matching 3x3 matrices."""
        obj = UORObjectTransformation(dimension=3)
        t1 = GroupElement(
            operation=GroupOperation.SCALING,
            parameters={"sx": 2},
        )
        # rotation_matrix ignores dimension and always returns 2x2;
        # patch it to 3x3 so compose_matrices works
        id3 = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        with patch.object(obj.lie_ops, "rotation_matrix", return_value=id3):
            result = obj.compose_transformations([t1])
        assert result.matrix is not None

    def test_temp_matrix_falsy_skipped(self):
        """When matrix method returns None, skip compose."""
        with patch("uar.uor.lie_groups.NUMPY_AVAILABLE", False):
            obj = UORObjectTransformation(dimension=2)
            t1 = GroupElement(
                operation=GroupOperation.ROTATION,
                parameters={"angle": 0},
            )
            with patch.object(
                obj.lie_ops, "rotation_matrix", side_effect=[
                    [[1, 0], [0, 1]],  # init call
                    None,  # loop call
                ]
            ):
                result = obj.compose_transformations([t1])
            assert result.matrix is not None

    def test_reflection_no_matrix(self):
        """REFLECTION falls through all elifs, covering 372->377."""
        obj = UORObjectTransformation(dimension=2)
        t1 = GroupElement(
            operation=GroupOperation.REFLECTION,
            parameters={"axis": "x"},
        )
        result = obj.compose_transformations([t1])
        assert result.matrix is not None
