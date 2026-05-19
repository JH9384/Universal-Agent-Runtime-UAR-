"""Atlas Embeddings Integration Layer for UAR.

This module provides integration with the UOR Foundation's
atlas-embeddings (Golden Seed Vector) for mathematical structure
and symmetry representations.

The Golden Seed Vector represents a universal mathematical language
for describing symmetry and structure, embedding Atlas to E8.

Key concepts:
- Golden Seed Vector: Complete embedding structure mapping Atlas to E8
- E8 Lie Group: Exceptional Lie group with 248 dimensions
- Universal mathematical language for describing symmetry
- Integration with UOR object references for artifact identification
"""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass
import numpy as np

from .uor_integration import UORObject, ObjectMode

logger = logging.getLogger(__name__)


@dataclass
class GoldenSeedVector:
    """Represents the Golden Seed Vector for Atlas to E8 embedding."""

    dimensions: int = 248  # E8 has 248 dimensions
    vector_data: Optional[np.ndarray] = None
    symmetry_group: str = "E8"
    metadata: Dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        if self.vector_data is None:
            self.vector_data = np.zeros(self.dimensions)

    def generate_random_seed(self) -> np.ndarray:
        """Generate a random Golden Seed Vector."""
        self.vector_data = np.random.randn(self.dimensions)
        return self.vector_data

    def normalize(self) -> np.ndarray:
        """Normalize the vector to unit length."""
        if self.vector_data is None:
            return np.zeros(self.dimensions)
        norm = np.linalg.norm(self.vector_data)
        if norm > 0:
            self.vector_data = self.vector_data / norm
        return self.vector_data

    def compute_symmetry(self) -> Dict[str, float]:
        """Compute symmetry properties of the vector."""
        if self.vector_data is None:
            return {}

        return {
            "mean": float(np.mean(self.vector_data)),
            "std": float(np.std(self.vector_data)),
            "norm": float(np.linalg.norm(self.vector_data)),
            "entropy": float(-np.sum(
                np.abs(self.vector_data) *
                np.log(np.abs(self.vector_data) + 1e-10)
            )),
        }

    def wrap_with_uor(self, source: str = "atlas_embeddings") -> UORObject:
        """Wrap the Golden Seed Vector in a UOR object."""
        uor_obj = UORObject(
            data={
                "dimensions": self.dimensions,
                "symmetry_group": self.symmetry_group,
                "symmetry_properties": self.compute_symmetry(),
            },
            mode=ObjectMode.IMMUTABLE_SINGULAR
        )
        uor_obj.compute_digest()
        uor_obj.add_provenance(source, "golden_seed_vector")
        uor_obj.add_schema_extension("golden_seed", True)
        uor_obj.add_schema_extension("symmetry_group", self.symmetry_group)

        return uor_obj


class AtlasEmbeddingsIntegrator:
    """Main Atlas Embeddings integration coordinator for UAR."""

    def __init__(self):
        self.enabled = True
        self.vector_cache: Dict[str, GoldenSeedVector] = {}

    def create_golden_seed(
        self,
        dimensions: int = 248,
        random: bool = True
    ) -> GoldenSeedVector:
        """Create a Golden Seed Vector."""
        seed = GoldenSeedVector(dimensions=dimensions)
        if random:
            seed.generate_random_seed()
            seed.normalize()

        return seed

    def compute_similarity(
        self,
        seed1: GoldenSeedVector,
        seed2: GoldenSeedVector,
        method: str = "cosine"
    ) -> float:
        """Compute similarity between two Golden Seed Vectors."""
        if seed1.vector_data is None or seed2.vector_data is None:
            return 0.0

        if method == "cosine":
            dot_product = np.dot(seed1.vector_data, seed2.vector_data)
            norm1 = np.linalg.norm(seed1.vector_data)
            norm2 = np.linalg.norm(seed2.vector_data)
            similarity = dot_product / (norm1 * norm2 + 1e-8)
        elif method == "euclidean":
            distance = np.linalg.norm(seed1.vector_data - seed2.vector_data)
            similarity = 1.0 / (1.0 + distance)
        else:
            raise ValueError(f"Unknown similarity method: {method}")

        return float(similarity)

    def transform_vector(
        self,
        seed: GoldenSeedVector,
        transformation_matrix: np.ndarray
    ) -> GoldenSeedVector:
        """Apply a transformation matrix to a Golden Seed Vector."""
        if seed.vector_data is None:
            return seed

        transformed_data = np.dot(transformation_matrix, seed.vector_data)
        new_seed = GoldenSeedVector(
            dimensions=seed.dimensions,
            symmetry_group=seed.symmetry_group,
            metadata=seed.metadata.copy()
        )
        new_seed.vector_data = transformed_data
        new_seed.normalize()

        return new_seed

    def integrate_with_uor(
        self,
        seed: GoldenSeedVector,
        source: str = "atlas_embeddings"
    ) -> UORObject:
        """Integrate Golden Seed Vector with UOR system."""
        uor_obj = seed.wrap_with_uor(source)

        # Add schema extensions for embedding tracking
        uor_obj.add_schema_extension("atlas_embedding", True)
        uor_obj.add_schema_extension(
            "vector_dimensions", seed.dimensions
        )

        return uor_obj

    def batch_process_embeddings(
        self,
        data_list: List[Any],
        dimensions: int = 248
    ) -> List[UORObject]:
        """Process multiple data items into embeddings with UOR objects."""
        results = []

        for data in data_list:
            # Create seed
            seed = self.create_golden_seed(dimensions=dimensions)

            # Integrate with UOR
            uor_obj = self.integrate_with_uor(seed)
            uor_obj.add_schema_extension("source_data", str(data))
            results.append(uor_obj)

        return results


# Global Atlas Embeddings integrator instance
_atlas_integrator: Optional[AtlasEmbeddingsIntegrator] = None


def get_atlas_integrator() -> AtlasEmbeddingsIntegrator:
    """Get the global Atlas Embeddings integrator instance."""
    global _atlas_integrator
    if _atlas_integrator is None:
        _atlas_integrator = AtlasEmbeddingsIntegrator()
    return _atlas_integrator


def reset_atlas_integrator():
    """Reset the global Atlas Embeddings integrator (useful for testing)."""
    global _atlas_integrator
    _atlas_integrator = None


def create_golden_seed(
    dimensions: int = 248,
    random: bool = True
) -> GoldenSeedVector:
    """Convenience function to create a Golden Seed Vector."""
    integrator = get_atlas_integrator()
    return integrator.create_golden_seed(dimensions, random)
