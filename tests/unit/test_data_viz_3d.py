"""Tests for uar.skills.data_viz_3d."""

from unittest.mock import MagicMock

from uar.skills.data_viz_3d import (
    _sphere_mesh,
    _torus_mesh,
    _klein_bottle_mesh,
    _mobius_strip_mesh,
    _hyperboloid_mesh,
    data_viz_3d,
)


class TestSphereMesh:
    def test_default(self):
        mesh = _sphere_mesh()
        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0
        assert len(mesh["vertices"]) == mesh["vertex_count"]

    def test_custom_params(self):
        mesh = _sphere_mesh(radius=2.0, segments=8, rings=4)
        assert mesh["vertex_count"] == 45  # (4+1)*(8+1)


class TestTorusMesh:
    def test_default(self):
        mesh = _torus_mesh()
        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0

    def test_custom(self):
        mesh = _torus_mesh(
            major_radius=2.0, minor_radius=0.5,
            major_segments=8, minor_segments=4,
        )
        assert mesh["vertex_count"] == 45


class TestKleinBottleMesh:
    def test_default(self):
        mesh = _klein_bottle_mesh()
        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0


class TestMobiusStripMesh:
    def test_default(self):
        mesh = _mobius_strip_mesh()
        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0


class TestHyperboloidMesh:
    def test_default(self):
        mesh = _hyperboloid_mesh()
        assert mesh["vertex_count"] > 0
        assert mesh["face_count"] > 0


class TestDataViz3D:
    def test_sphere(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"mesh_type": "sphere", "radius": 2.0}
        ctx.goal.user_intent = "test"
        result = data_viz_3d(ctx)
        assert result["status"] == "completed"
        assert result["result"]["mesh_type"] == "sphere"

    def test_torus(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"mesh_type": "torus"}
        ctx.goal.user_intent = "test"
        result = data_viz_3d(ctx)
        assert result["result"]["mesh_type"] == "torus"

    def test_klein_bottle(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"mesh_type": "klein_bottle"}
        ctx.goal.user_intent = "test"
        result = data_viz_3d(ctx)
        assert result["result"]["mesh_type"] == "klein_bottle"

    def test_mobius_strip(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"mesh_type": "mobius_strip"}
        ctx.goal.user_intent = "test"
        result = data_viz_3d(ctx)
        assert result["result"]["mesh_type"] == "mobius_strip"

    def test_hyperboloid(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"mesh_type": "hyperboloid"}
        ctx.goal.user_intent = "test"
        result = data_viz_3d(ctx)
        assert result["result"]["mesh_type"] == "hyperboloid"

    def test_default_mesh(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.user_intent = "test"
        result = data_viz_3d(ctx)
        assert result["result"]["mesh_type"] == "sphere"

    def test_unknown_mesh(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"mesh_type": "unknown"}
        ctx.goal.user_intent = "test"
        result = data_viz_3d(ctx)
        assert result["result"]["mesh_type"] == "unknown"
        assert "vertex_count" in result["result"]
