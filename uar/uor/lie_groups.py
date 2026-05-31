"""Lie groups integration for UOR mathematical foundations.

Provides Lie group operations and group theory transformations for
UOR object spaces, enabling advanced mathematical modeling of
object relationships and transformations.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

try:
    import numpy as np

    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logging.warning("NumPy not available. Install with: pip install numpy")

logger = logging.getLogger(__name__)


class GroupOperation(Enum):
    """Types of group operations."""

    ROTATION = "rotation"
    TRANSLATION = "translation"
    SCALING = "scaling"
    REFLECTION = "reflection"
    COMPOSITION = "composition"
    INVERSION = "inversion"

    def __eq__(self, other):
        if isinstance(other, GroupOperation):
            return self.value == other.value
        return self.value == other

    def __hash__(self):
        return hash(self.value)


@dataclass
class GroupElement:
    """Represents an element in a Lie group."""

    operation: GroupOperation
    parameters: Dict[str, Any]
    dimension: int = 2
    matrix: Optional[List[List[float]]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation": self.operation.value,
            "parameters": self.parameters,
            "dimension": self.dimension,
            "matrix": self.matrix,
        }


class LieGroupOperations:
    """Lie group operations for UOR object transformations."""

    def __init__(self, dimension: int = 2):
        """Initialize Lie group operations.

        Args:
            dimension: Dimension of the transformation space (default 2)
        """
        self.dimension = dimension

    def rotation_matrix(self, angle: float) -> List[List[float]]:
        """Generate rotation matrix for given angle.

        Args:
            angle: Rotation angle in radians

        Returns:
            Rotation matrix
        """
        if NUMPY_AVAILABLE:
            theta = np.array(angle)
            c, s = np.cos(theta), np.sin(theta)
            return [[c, -s], [s, c]]
        else:
            import math

            c, s = math.cos(angle), math.sin(angle)
            return [[c, -s], [s, c]]

    def translation_matrix(self, dx: float, dy: float) -> List[List[float]]:
        """Generate translation matrix.

        Args:
            dx: Translation in x direction
            dy: Translation in y direction

        Returns:
            Translation matrix
        """
        return [[1, 0, dx], [0, 1, dy], [0, 0, 1]]

    def scaling_matrix(
        self, sx: float, sy: Optional[float] = None
    ) -> List[List[float]]:
        """Generate scaling matrix.

        Args:
            sx: Scale factor in x direction
            sy: Scale factor in y direction (defaults to sx for uniform scaling)

        Returns:
            Scaling matrix
        """  # noqa: E501
        if sy is None:
            sy = sx
        return [[sx, 0, 0], [0, sy, 0], [0, 0, 1]]

    def reflection_matrix(self, axis: str = "x") -> List[List[float]]:
        """Generate reflection matrix.

        Args:
            axis: Axis to reflect across ('x' or 'y')

        Returns:
            Reflection matrix
        """
        if axis == "x":
            return [[1, 0, 0], [0, -1, 0], [0, 0, 1]]
        elif axis == "y":
            return [[-1, 0, 0], [0, 1, 0], [0, 0, 1]]
        else:
            raise ValueError(f"Invalid axis: {axis}. Use 'x' or 'y'")

    def compose_matrices(
        self, m1: List[List[float]], m2: List[List[float]]
    ) -> List[List[float]]:
        """Compose two transformation matrices.

        Args:
            m1: First transformation matrix
            m2: Second transformation matrix

        Returns:
            Composed matrix (m1 * m2)
        """
        if NUMPY_AVAILABLE:
            result = np.dot(np.array(m1), np.array(m2))  # type: ignore
            return result.tolist()
        else:
            # Manual matrix multiplication
            rows1, cols1 = len(m1), len(m1[0])
            rows2, cols2 = len(m2), len(m2[0])
            if cols1 != rows2:
                raise ValueError(
                    "Matrix dimensions incompatible for multiplication"
                )

            result = [[0 for _ in range(cols2)] for _ in range(rows1)]
            for i in range(rows1):
                for j in range(cols2):
                    for k in range(cols1):
                        result[i][j] += m1[i][k] * m2[k][j]
            return result

    def invert_matrix(self, matrix: List[List[float]]) -> List[List[float]]:
        """Invert a transformation matrix.

        Args:
            matrix: Transformation matrix to invert

        Returns:
            Inverted matrix
        """
        if NUMPY_AVAILABLE:
            inv_matrix = np.linalg.inv(np.array(matrix))  # type: ignore
            return inv_matrix.tolist()
        else:
            # For simple 2D/3D transformations, use analytical formulas
            if len(matrix) == 2 and len(matrix[0]) == 2:
                # 2x2 matrix inverse
                det = matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
                if abs(det) < 1e-10:
                    raise ValueError("Matrix is singular, cannot invert")
                inv: List[List[float]] = [
                    [matrix[1][1] / det, -matrix[0][1] / det],
                    [-matrix[1][0] / det, matrix[0][0] / det],
                ]
                return inv
            else:
                raise NotImplementedError(
                    "Matrix inversion requires NumPy for general matrices"
                )

    def apply_transformation(
        self,
        point: List[float],
        transformation: GroupElement,
    ) -> List[float]:
        """Apply a Lie group transformation to a point.

        Args:
            point: Point coordinates [x, y, ...]
            transformation: Group element representing transformation

        Returns:
            Transformed point coordinates
        """
        if transformation.matrix is None:
            # Generate matrix from parameters
            op = transformation.operation
            params = transformation.parameters

            if op == GroupOperation.ROTATION:
                matrix = self.rotation_matrix(params["angle"])
            elif op == GroupOperation.TRANSLATION:
                matrix = self.translation_matrix(params["dx"], params["dy"])
            elif op == GroupOperation.SCALING:
                matrix = self.scaling_matrix(params["sx"], params.get("sy"))
            elif op == GroupOperation.REFLECTION:
                matrix = self.reflection_matrix(params.get("axis", "x"))
            else:
                raise ValueError(f"Unsupported operation: {op}")
        else:
            matrix = transformation.matrix

        # Apply matrix to point
        if NUMPY_AVAILABLE:
            point_arr = np.array(point + [1])  # type: ignore
            transformed = np.dot(np.array(matrix), point_arr)  # type: ignore
            return transformed[:-1].tolist()  # type: ignore
        else:
            # Manual matrix-vector multiplication
            if len(matrix) == 3:  # 3x3 matrix with homogeneous coordinates
                point_homogeneous = point + [1]
                result: List[float] = [0.0] * len(matrix)
                for i in range(len(matrix)):
                    for j in range(len(matrix[0])):
                        result[i] += matrix[i][j] * point_homogeneous[j]
                return result[:-1]
            else:
                point_arr = point  # type: ignore[assignment]
                result_vec: List[float] = [0.0] * len(matrix)
                for i in range(len(matrix)):
                    for j in range(len(matrix[0])):
                        result_vec[i] += matrix[i][j] * point_arr[j]
                return result_vec

    def create_group_element(
        self,
        operation: GroupOperation,
        parameters: Dict[str, Any],
    ) -> GroupElement:
        """Create a group element from operation and parameters.

        Args:
            operation: Type of group operation
            parameters: Operation parameters

        Returns:
            Group element
        """
        return GroupElement(
            operation=operation,
            parameters=parameters,
            dimension=self.dimension,
        )

    def get_lie_algebra_basis(self) -> Dict[str, List[List[float]]]:
        """Get basis elements for the Lie algebra.

        Returns:
            Dictionary of basis element matrices
        """
        # For SE(2) group (special Euclidean group in 2D)
        # Basis for translations and rotation
        return {
            "translation_x": [[0, 0, 1], [0, 0, 0], [0, 0, 0]],
            "translation_y": [[0, 0, 0], [0, 0, 1], [0, 0, 0]],
            "rotation": [[0, -1, 0], [1, 0, 0], [0, 0, 0]],
        }

    def exponential_map(
        self, algebra_element: List[List[float]], t: float = 1.0
    ) -> List[List[float]]:
        """Compute exponential map from Lie algebra to Lie group.

        Args:
            algebra_element: Element of the Lie algebra (skew-symmetric matrix)
            t: Parameter for the exponential map

        Returns:
            Group element (matrix)
        """
        if NUMPY_AVAILABLE:
            A = np.array(algebra_element) * t  # type: ignore
            # Matrix exponential: exp(A) = I + A + A^2/2! + A^3/3! + ...
            exp_A = np.eye(len(A))  # type: ignore
            term = np.eye(len(A))  # type: ignore
            for i in range(1, 20):  # 20 terms for convergence
                term = np.dot(term, A) / i  # type: ignore
                exp_A = exp_A + term  # type: ignore
            return exp_A.tolist()  # type: ignore
        else:
            raise NotImplementedError(
                "Exponential map requires NumPy for series computation"
            )


class UORObjectTransformation:
    """Applies Lie group transformations to UOR objects."""

    def __init__(self, dimension: int = 2):
        """Initialize object transformation.

        Args:
            dimension: Dimension of transformation space
        """
        self.lie_ops = LieGroupOperations(dimension)

    def transform_object_position(
        self,
        position: List[float],
        transformations: List[GroupElement],
    ) -> List[float]:
        """Apply multiple transformations to an object position.

        Args:
            position: Original position [x, y, ...]
            transformations: List of transformations to apply in order

        Returns:
            Transformed position
        """
        current_position = position
        for transform in transformations:
            current_position = self.lie_ops.apply_transformation(
                current_position, transform
            )
        return current_position

    def compose_transformations(
        self,
        transformations: List[GroupElement],
    ) -> GroupElement:
        """Compose multiple transformations into a single transformation.

        Args:
            transformations: List of transformations to compose

        Returns:
            Composed transformation element
        """
        if not transformations:
            raise ValueError("Cannot compose empty transformation list")

        # Start with identity matrix
        matrix = self.lie_ops.rotation_matrix(0)  # Identity for rotation
        if len(transformations[0].parameters) > 1:
            matrix = self.lie_ops.translation_matrix(0, 0)

        for transform in transformations:
            if transform.matrix:
                matrix = self.lie_ops.compose_matrices(
                    matrix, transform.matrix
                )
            else:
                # Generate matrix from transformation
                temp_matrix = None
                op = transform.operation
                params = transform.parameters

                if op == GroupOperation.ROTATION:
                    temp_matrix = self.lie_ops.rotation_matrix(params["angle"])
                elif op == GroupOperation.TRANSLATION:
                    temp_matrix = self.lie_ops.translation_matrix(
                        params["dx"], params["dy"]
                    )
                elif op == GroupOperation.SCALING:
                    temp_matrix = self.lie_ops.scaling_matrix(
                        params["sx"], params.get("sy")
                    )

                if temp_matrix:
                    matrix = self.lie_ops.compose_matrices(matrix, temp_matrix)

        return GroupElement(
            operation=GroupOperation.COMPOSITION,
            parameters={"composed_count": len(transformations)},
            dimension=self.lie_ops.dimension,
            matrix=matrix,
        )
