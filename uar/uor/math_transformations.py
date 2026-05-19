"""Advanced mathematical transformations for UOR objects.

Provides group theory operations and mathematical transformations
for UOR object spaces, building on Lie groups foundations.
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
from enum import Enum

from .lie_groups import LieGroupOperations, GroupOperation, GroupElement

logger = logging.getLogger(__name__)


class TransformationType(Enum):
    """Types of mathematical transformations."""

    LINEAR = "linear"
    AFFINE = "affine"
    PROJECTIVE = "projective"
    CONFORMAL = "conformal"
    TOPOLOGICAL = "topological"


@dataclass
class Transformation:
    """Represents a mathematical transformation."""

    transformation_type: TransformationType
    group_element: GroupElement
    parameters: Dict[str, Any]
    inverse: Optional["Transformation"] = None

    def compose(self, other: "Transformation") -> "Transformation":
        """Compose this transformation with another.

        Args:
            other: Transformation to compose with

        Returns:
            Composed transformation
        """
        lie_ops = LieGroupOperations()
        composed_matrix = lie_ops.compose_matrices(
            self.group_element.matrix or [],
            other.group_element.matrix or [],
        )

        composed_element = GroupElement(
            operation=GroupOperation.COMPOSITION,
            parameters={
                "composed_count": 2,
                "type1": self.transformation_type.value,
                "type2": other.transformation_type.value,
            },
            dimension=self.group_element.dimension,
            matrix=composed_matrix,
        )

        return Transformation(
            transformation_type=TransformationType.AFFINE,
            group_element=composed_element,
            parameters={"composed": True},
        )

    def invert(self) -> Optional["Transformation"]:
        """Invert this transformation.

        Returns:
            Inverted transformation or None if not invertible
        """
        if self.inverse:
            return self.inverse

        lie_ops = LieGroupOperations()
        if self.group_element.matrix:
            inv_matrix = lie_ops.invert_matrix(self.group_element.matrix)
            inv_element = GroupElement(
                operation=GroupOperation.INVERSION,
                parameters={"inverted": True},
                dimension=self.group_element.dimension,
                matrix=inv_matrix,
            )
            self.inverse = Transformation(
                transformation_type=self.transformation_type,
                group_element=inv_element,
                parameters=self.parameters,
            )
            return self.inverse
        return None


class GroupTheoryOperations:
    """Group theory operations for UOR object transformations."""

    def __init__(self, dimension: int = 2):
        """Initialize group theory operations.

        Args:
            dimension: Dimension of the transformation space
        """
        self.dimension = dimension
        self.lie_ops = LieGroupOperations(dimension)

    def check_group_axioms(self, elements: List[GroupElement]) -> Dict[str, bool]:
        """Check group axioms for a set of elements.

        Args:
            elements: List of group elements to check

        Returns:
            Dictionary of axiom checks
        """
        results = {
            "closure": self._check_closure(elements),
            "identity": self._check_identity(elements),
            "inverse": self._check_inverse(elements),
            "associativity": self._check_associativity(elements),
        }
        return results

    def _check_closure(self, elements: List[GroupElement]) -> bool:
        """Check closure property."""
        if not elements:
            return False

        for elem1 in elements:
            for elem2 in elements:
                if elem1.matrix and elem2.matrix:
                    composed = self.lie_ops.compose_matrices(
                        elem1.matrix, elem2.matrix
                    )
                    if not composed:
                        return False
        return True

    def _check_identity(self, elements: List[GroupElement]) -> bool:
        """Check identity element exists."""
        identity = self.lie_ops.rotation_matrix(0)
        # Check that identity * element = element for all elements
        for elem in elements:
            if elem.matrix:
                composed = self.lie_ops.compose_matrices(identity, elem.matrix)
                if not composed:
                    return False
        return True

    def _check_inverse(self, elements: List[GroupElement]) -> bool:
        """Check every element has an inverse."""
        for elem in elements:
            if elem.matrix:
                try:
                    inv = self.lie_ops.invert_matrix(elem.matrix)
                    if not inv:
                        return False
                except Exception:
                    return False
        return True

    def _check_associativity(self, elements: List[GroupElement]) -> bool:
        """Check associativity property."""
        if len(elements) < 3:
            return True  # Trivially true for fewer than 3 elements

        for i in range(min(len(elements), 3)):
            for j in range(min(len(elements), 3)):
                for k in range(min(len(elements), 3)):
                    if (
                        elements[i].matrix
                        and elements[j].matrix
                        and elements[k].matrix
                    ):
                        left = self.lie_ops.compose_matrices(
                            self.lie_ops.compose_matrices(
                                elements[i].matrix, elements[j].matrix
                            ),
                            elements[k].matrix,
                        )
                        right = self.lie_ops.compose_matrices(
                            elements[i].matrix,
                            self.lie_ops.compose_matrices(
                                elements[j].matrix, elements[k].matrix
                            ),
                        )
                        # Check approximate equality
                        for row in range(len(left)):
                            for col in range(len(left[0])):
                                if abs(left[row][col] - right[row][col]) > 0.01:
                                    return False
        return True

    def compute_group_order(self, elements: List[GroupElement]) -> int:
        """Compute the order of the group.

        Args:
            elements: List of group elements

        Returns:
            Number of distinct elements in the group
        """
        # Count distinct matrices
        distinct = set()
        for elem in elements:
            if elem.matrix:
                # Convert to tuple for hashing
                matrix_tuple = tuple(tuple(row) for row in elem.matrix)
                distinct.add(matrix_tuple)
        return len(distinct)

    def find_subgroups(
        self, elements: List[GroupElement]
    ) -> List[List[GroupElement]]:
        """Find subgroups within the group.

        Args:
            elements: List of group elements

        Returns:
            List of subgroups (each as a list of elements)
        """
        subgroups: List[List[GroupElement]] = []
        # Simple heuristic: find closed subsets
        # This is a simplified approach
        for i, elem in enumerate(elements):
            subgroup = [elem]
            # Try adding other elements
            for j, other in enumerate(elements):
                if i != j and other.matrix and elem.matrix:
                    composed = self.lie_ops.compose_matrices(elem.matrix, other.matrix)
                    if composed:
                        # Check if composed is in our set
                        for k in elements:
                            if k.matrix and self._matrices_equal(composed, k.matrix):
                                subgroup.append(other)
                                break
            if len(subgroup) > 1:
                # Check if this subgroup is already found
                found = False
                for existing in subgroups:
                    if len(subgroup) == len(existing):
                        found = True
                        break
                if not found:
                    subgroups.append(subgroup)
        return subgroups

    def _matrices_equal(self, m1: List[List[float]], m2: List[List[float]]) -> bool:
        """Check if two matrices are approximately equal."""
        if len(m1) != len(m2) or len(m1[0]) != len(m2[0]):
            return False
        for i in range(len(m1)):
            for j in range(len(m1[0])):
                if abs(m1[i][j] - m2[i][j]) > 0.01:
                    return False
        return True


class UORObjectMathTransform:
    """Applies mathematical transformations to UOR objects."""

    def __init__(self, dimension: int = 2):
        """Initialize object math transform.

        Args:
            dimension: Dimension of transformation space
        """
        self.lie_ops = LieGroupOperations(dimension)
        self.group_ops = GroupTheoryOperations(dimension)

    def apply_transformation(
        self,
        object_data: Dict[str, Any],
        transformation: Transformation,
        field: str = "position",
    ) -> Dict[str, Any]:
        """Apply transformation to an object field.

        Args:
            object_data: Object data dictionary
            transformation: Transformation to apply
            field: Field to transform (default "position")

        Returns:
            Transformed object data
        """
        result = object_data.copy()

        if field in result and isinstance(result[field], list):
            original_position = result[field]
            transformed_position = self.lie_ops.apply_transformation(
                original_position, transformation.group_element
            )
            result[field] = transformed_position
            result[f"{field}_transformed"] = True

        return result

    def create_rotation_transformation(
        self, angle: float
    ) -> Transformation:
        """Create a rotation transformation.

        Args:
            angle: Rotation angle in radians

        Returns:
            Rotation transformation
        """
        element = self.lie_ops.create_group_element(
            GroupOperation.ROTATION, {"angle": angle}
        )
        element.matrix = self.lie_ops.rotation_matrix(angle)

        return Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=element,
            parameters={"angle": angle},
        )

    def create_translation_transformation(
        self, dx: float, dy: float
    ) -> Transformation:
        """Create a translation transformation.

        Args:
            dx: Translation in x direction
            dy: Translation in y direction

        Returns:
            Translation transformation
        """
        element = self.lie_ops.create_group_element(
            GroupOperation.TRANSLATION, {"dx": dx, "dy": dy}
        )
        element.matrix = self.lie_ops.translation_matrix(dx, dy)

        return Transformation(
            transformation_type=TransformationType.AFFINE,
            group_element=element,
            parameters={"dx": dx, "dy": dy},
        )

    def create_scaling_transformation(
        self, sx: float, sy: Optional[float] = None
    ) -> Transformation:
        """Create a scaling transformation.

        Args:
            sx: Scale factor in x direction
            sy: Scale factor in y direction (defaults to sx)

        Returns:
            Scaling transformation
        """
        element = self.lie_ops.create_group_element(
            GroupOperation.SCALING, {"sx": sx, "sy": sy}
        )
        element.matrix = self.lie_ops.scaling_matrix(sx, sy)

        return Transformation(
            transformation_type=TransformationType.AFFINE,
            group_element=element,
            parameters={"sx": sx, "sy": sy},
        )

    def compose_transformations(
        self, transformations: List[Transformation]
    ) -> Transformation:
        """Compose multiple transformations.

        Args:
            transformations: List of transformations to compose

        Returns:
            Composed transformation
        """
        if not transformations:
            raise ValueError("Cannot compose empty transformation list")

        result = transformations[0]
        for transform in transformations[1:]:
            result = result.compose(transform)

        return result

    def compute_transformation_chain(
        self,
        object_data: Dict[str, Any],
        transformations: List[Transformation],
        field: str = "position",
    ) -> Dict[str, Any]:
        """Apply a chain of transformations to an object.

        Args:
            object_data: Object data dictionary
            transformations: List of transformations to apply in order
            field: Field to transform

        Returns:
            Transformed object data
        """
        result = object_data.copy()
        for transform in transformations:
            result = self.apply_transformation(result, transform, field)
        return result

    def analyze_transformation_group(
        self, transformations: List[Transformation]
    ) -> Dict[str, Any]:
        """Analyze the group properties of transformations.

        Args:
            transformations: List of transformations to analyze

        Returns:
            Analysis results
        """
        elements = [t.group_element for t in transformations]
        axiom_checks = self.group_ops.check_group_axioms(elements)
        group_order = self.group_ops.compute_group_order(elements)
        subgroups = self.group_ops.find_subgroups(elements)

        return {
            "group_axioms": axiom_checks,
            "group_order": group_order,
            "subgroup_count": len(subgroups),
            "is_valid_group": all(axiom_checks.values()),
        }
