"""Tests for uar.core.uor_vector_ops."""

import numpy as np
import pytest

from uar.core.uor_vector_ops import (
    UORVector,
    UORVectorOps,
    get_uor_vector_ops,
    reset_uor_vector_ops,
)
from uar.uor.math_transformations import Transformation, TransformationType


class TestUORVector:
    def test_compute_digest(self):
        v = UORVector(data=np.array([1.0, 2.0, 3.0]))
        digest = v.compute_digest()
        assert isinstance(digest, str)
        assert v.digest == digest


class TestUORVectorOps:
    def test_create_vector(self):
        ops = UORVectorOps()
        v = ops.create_vector(np.array([1.0, 2.0]), source="test")
        assert v.digest is not None
        assert len(v.provenance) > 0
        assert ops.get_vector_by_digest(v.digest) is v

    def test_cosine_similarity(self):
        ops = UORVectorOps()
        v1 = ops.create_vector(np.array([1.0, 0.0]))
        v2 = ops.create_vector(np.array([1.0, 0.0]))
        sim = ops.compute_similarity(v1, v2, method="cosine")
        assert pytest.approx(sim, 0.01) == 1.0

    def test_euclidean_similarity(self):
        ops = UORVectorOps()
        v1 = ops.create_vector(np.array([0.0, 0.0]))
        v2 = ops.create_vector(np.array([3.0, 4.0]))
        sim = ops.compute_similarity(v1, v2, method="euclidean")
        assert sim > 0

    def test_similarity_mismatched_shapes(self):
        ops = UORVectorOps()
        v1 = ops.create_vector(np.array([1.0, 2.0]))
        v2 = ops.create_vector(np.array([1.0, 2.0, 3.0]))
        with pytest.raises(ValueError):
            ops.compute_similarity(v1, v2)

    def test_similarity_unknown_method(self):
        ops = UORVectorOps()
        v1 = ops.create_vector(np.array([1.0, 2.0]))
        v2 = ops.create_vector(np.array([1.0, 2.0]))
        with pytest.raises(ValueError, match="Unknown similarity method"):
            ops.compute_similarity(v1, v2, method="unknown")

    def test_apply_transformation_with_matrix(self):
        ops = UORVectorOps()
        v = ops.create_vector(np.array([1.0]))
        matrix = np.array([2.0])
        xf = Transformation(
            transformation_type=TransformationType.LINEAR,
            group_element=type("GE", (), {"matrix": matrix})(),
            parameters={},
        )
        new_v = ops.apply_transformation(v, xf)
        assert new_v.data is not None
        assert len(new_v.provenance) > 0

    def test_apply_transformation_no_matrix(self):
        ops = UORVectorOps()
        v = ops.create_vector(np.array([1.0, 0.0]))
        xf = Transformation(
            transformation_type=TransformationType.AFFINE,
            group_element=type("GE", (), {"matrix": None})(),
            parameters={},
        )
        new_v = ops.apply_transformation(v, xf)
        np.testing.assert_array_equal(new_v.data, v.data)

    def test_batch_similarity(self):
        ops = UORVectorOps()
        query = ops.create_vector(np.array([1.0, 0.0]))
        vectors = [
            ops.create_vector(np.array([1.0, 0.0])),
            ops.create_vector(np.array([0.0, 1.0])),
            ops.create_vector(np.array([1.0, 2.0, 3.0])),  # mismatched
        ]
        results = ops.batch_similarity(query, vectors, top_k=2)
        assert len(results) <= 2
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

    def test_batch_similarity_no_top_k(self):
        ops = UORVectorOps()
        query = ops.create_vector(np.array([1.0, 0.0]))
        vectors = [ops.create_vector(np.array([1.0, 0.0]))]
        results = ops.batch_similarity(query, vectors)
        assert len(results) == 1


class TestGlobalOps:
    def test_get_and_reset(self):
        reset_uor_vector_ops()
        ops1 = get_uor_vector_ops()
        ops2 = get_uor_vector_ops()
        assert ops1 is ops2
        reset_uor_vector_ops()
        ops3 = get_uor_vector_ops()
        assert ops3 is not ops1
