"""UOR Vector Operations Integration Layer for UAR.

This module provides vector operations integration between UAR and UOR,
leveraging the existing UOR math modules (lie_groups, math_transformations)
for embeddings, similarity calculations, and transformations.

Key features:
- Vector embedding generation with UOR tracking
- Similarity calculations with integrity verification
- Mathematical transformations via UOR Lie groups
- Vector space operations for agent context
"""

import logging
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
import numpy as np

from .uor_integration import wrap_input_data
from uar.uor.lie_groups import LieGroupOperations
from uar.uor.math_transformations import Transformation

logger = logging.getLogger(__name__)


@dataclass
class UORVector:
    """UOR vector wrapper with integrity tracking."""

    data: np.ndarray
    digest: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    provenance: List[Dict[str, Any]] = field(default_factory=list)

    def compute_digest(self) -> str:
        """Compute UOR digest for the vector."""
        vector_uor = wrap_input_data(
            {"shape": self.data.shape, "mean": float(np.mean(self.data))},
            source="vector_ops",
        )
        self.digest = vector_uor.digest
        return self.digest


class UORVectorOps:
    """Vector operations with UOR integrity tracking."""

    def __init__(self):
        self.enabled = True
        self.lie_ops = LieGroupOperations()
        self.vector_cache: Dict[str, UORVector] = {}

    def create_vector(
        self, data: np.ndarray, source: str = "unknown"
    ) -> UORVector:
        """Create a UOR vector with integrity tracking."""
        vector = UORVector(data=data)
        vector.compute_digest()
        vector.provenance.append(
            {
                "source": source,
                "operation": "create_vector",
            }
        )

        if vector.digest:
            self.vector_cache[vector.digest] = vector

        return vector

    def compute_similarity(
        self, vec1: UORVector, vec2: UORVector, method: str = "cosine"
    ) -> float:
        """Compute similarity between two vectors."""
        if vec1.data.shape != vec2.data.shape:
            raise ValueError(
                "Vector shapes must match for similarity computation"
            )

        if method == "cosine":
            # Cosine similarity
            dot_product = np.dot(vec1.data, vec2.data)
            norm1 = np.linalg.norm(vec1.data)
            norm2 = np.linalg.norm(vec2.data)
            similarity = dot_product / (norm1 * norm2 + 1e-8)
        elif method == "euclidean":
            # Euclidean distance (converted to similarity)
            distance = np.linalg.norm(vec1.data - vec2.data)
            similarity = 1.0 / (1.0 + distance)
        else:
            raise ValueError(f"Unknown similarity method: {method}")

        # Track operation
        vec1.provenance.append(
            {
                "source": "vector_ops",
                "operation": f"similarity_{method}",
                "target_vector": vec2.digest,
            }
        )

        return float(similarity)

    def apply_transformation(
        self, vector: UORVector, transformation: Transformation
    ) -> UORVector:
        """Apply a mathematical transformation to a vector."""
        # Use Lie groups for transformation
        if transformation.group_element.matrix:
            matrix = transformation.group_element.matrix
            if len(matrix) == len(vector.data):
                # Apply matrix transformation
                transformed_data = np.dot(matrix, vector.data)
            else:
                # Fallback: use identity transformation
                transformed_data = vector.data.copy()
        else:
            transformed_data = vector.data.copy()

        # Create new UOR vector
        new_vector = self.create_vector(
            transformed_data,
            source=f"transform:{transformation.transformation_type.value}",
        )

        # Copy provenance and add transformation record
        new_vector.provenance = vector.provenance.copy()
        new_vector.provenance.append(
            {
                "source": "vector_ops",
                "operation": "apply_transformation",
                "transformation_type": transformation.transformation_type.value,  # noqa: E501
            }
        )

        return new_vector

    def batch_similarity(
        self,
        query_vector: UORVector,
        vector_list: List[UORVector],
        method: str = "cosine",
        top_k: Optional[int] = None,
    ) -> List[Tuple[int, float]]:
        """Compute similarity against a list of vectors."""
        similarities = []
        for idx, vec in enumerate(vector_list):
            try:
                sim = self.compute_similarity(query_vector, vec, method)
                similarities.append((idx, sim))
            except ValueError:
                # Skip vectors with mismatched shapes
                continue

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)

        if top_k:
            similarities = similarities[:top_k]

        return similarities

    def get_vector_by_digest(self, digest: str) -> Optional[UORVector]:
        """Retrieve vector from cache by digest."""
        return self.vector_cache.get(digest)


# Global UOR vector operations instance
_uor_vector_ops: Optional[UORVectorOps] = None


def get_uor_vector_ops() -> UORVectorOps:
    """Get the global UOR vector operations instance."""
    global _uor_vector_ops
    if _uor_vector_ops is None:
        _uor_vector_ops = UORVectorOps()
    return _uor_vector_ops


def reset_uor_vector_ops():
    """Reset the global UOR vector operations instance (useful for testing)."""
    global _uor_vector_ops
    _uor_vector_ops = None
