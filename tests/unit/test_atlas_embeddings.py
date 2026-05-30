"""Tests for uar.core.atlas_embeddings."""

import numpy as np
import pytest

from uar.core.atlas_embeddings import (
    GoldenSeedVector,
    AtlasEmbeddingsIntegrator,
)


class TestGoldenSeedVector:
    def test_default_init(self):
        seed = GoldenSeedVector()
        assert seed.dimensions == 248
        assert seed.symmetry_group == "E8"
        assert seed.vector_data is not None
        assert len(seed.vector_data) == 248

    def test_post_init_metadata(self):
        seed = GoldenSeedVector(metadata=None)
        assert seed.metadata == {}

    def test_generate_random_seed(self):
        seed = GoldenSeedVector()
        vec = seed.generate_random_seed()
        assert len(vec) == 248
        assert not np.allclose(vec, 0)

    def test_normalize(self):
        seed = GoldenSeedVector()
        seed.generate_random_seed()
        normalized = seed.normalize()
        norm = np.linalg.norm(normalized)
        assert abs(norm - 1.0) < 1e-6

    def test_normalize_zero_vector(self):
        seed = GoldenSeedVector()
        normalized = seed.normalize()
        assert np.allclose(normalized, 0)

    def test_compute_symmetry(self):
        seed = GoldenSeedVector()
        seed.generate_random_seed()
        props = seed.compute_symmetry()
        assert "mean" in props
        assert "std" in props
        assert "norm" in props
        assert "entropy" in props

    def test_compute_symmetry_none_vector(self):
        seed = GoldenSeedVector()
        seed.vector_data = None
        assert seed.compute_symmetry() == {}

    def test_wrap_with_uor(self):
        seed = GoldenSeedVector()
        seed.generate_random_seed()
        uor = seed.wrap_with_uor()
        assert uor.data["dimensions"] == 248
        assert uor.data["symmetry_group"] == "E8"
        assert "symmetry_properties" in uor.data


class TestAtlasEmbeddingsIntegrator:
    def test_create_golden_seed_random(self):
        integrator = AtlasEmbeddingsIntegrator()
        seed = integrator.create_golden_seed(dimensions=64, random=True)
        assert seed.dimensions == 64
        assert len(seed.vector_data) == 64

    def test_create_golden_seed_not_random(self):
        integrator = AtlasEmbeddingsIntegrator()
        seed = integrator.create_golden_seed(dimensions=64, random=False)
        assert np.allclose(seed.vector_data, 0)

    def test_compute_similarity_cosine(self):
        integrator = AtlasEmbeddingsIntegrator()
        s1 = integrator.create_golden_seed(dimensions=64, random=True)
        s2 = integrator.create_golden_seed(dimensions=64, random=True)
        sim = integrator.compute_similarity(s1, s2, method="cosine")
        assert -1.0 <= sim <= 1.0

    def test_compute_similarity_euclidean(self):
        integrator = AtlasEmbeddingsIntegrator()
        s1 = integrator.create_golden_seed(dimensions=64, random=True)
        s2 = integrator.create_golden_seed(dimensions=64, random=True)
        sim = integrator.compute_similarity(s1, s2, method="euclidean")
        assert 0.0 <= sim <= 1.0

    def test_compute_similarity_none_vector(self):
        integrator = AtlasEmbeddingsIntegrator()
        s1 = GoldenSeedVector(dimensions=64)
        s1.vector_data = None
        s2 = integrator.create_golden_seed(dimensions=64, random=True)
        sim = integrator.compute_similarity(s1, s2)
        assert sim == 0.0

    def test_compute_similarity_unknown_method(self):
        integrator = AtlasEmbeddingsIntegrator()
        s1 = integrator.create_golden_seed(dimensions=64, random=True)
        s2 = integrator.create_golden_seed(dimensions=64, random=True)
        with pytest.raises(ValueError, match="Unknown similarity"):
            integrator.compute_similarity(s1, s2, method="unknown")

    def test_transform_vector(self):
        integrator = AtlasEmbeddingsIntegrator()
        seed = integrator.create_golden_seed(dimensions=64, random=True)
        matrix = np.eye(64)
        result = integrator.transform_vector(seed, matrix)
        assert result.vector_data is not None
        assert len(result.vector_data) == 64

    def test_transform_vector_none(self):
        integrator = AtlasEmbeddingsIntegrator()
        seed = GoldenSeedVector(dimensions=64)
        seed.vector_data = None
        matrix = np.eye(64)
        result = integrator.transform_vector(seed, matrix)
        assert result is seed
