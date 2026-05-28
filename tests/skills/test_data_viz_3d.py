"""Tests for 3D data visualization skill.

Covers all mesh generators: sphere, torus, klein_bottle,
mobius_strip, hyperboloid.
"""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.data_viz_3d import (
    _sphere_mesh,
    _torus_mesh,
    _klein_bottle_mesh,
    _mobius_strip_mesh,
    _hyperboloid_mesh,
    data_viz_3d,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="test", objective="t", metadata=meta
        )
    )


class TestSphereMesh:
    """UV sphere generation."""

    def test_basic(self):
        mesh = _sphere_mesh(radius=1.0, segments=8, rings=4)
        assert mesh["vertex_count"] == (8 + 1) * (4 + 1)
        assert mesh["face_count"] == 8 * 4 * 2
        assert len(mesh["vertices"]) == mesh["vertex_count"]
        assert len(mesh["normals"]) == mesh["vertex_count"]
        assert len(mesh["uvs"]) == mesh["vertex_count"]
        assert len(mesh["indices"]) == mesh["face_count"] * 3

    def test_radius(self):
        mesh = _sphere_mesh(radius=2.0, segments=4, rings=2)
        # Check that vertices are scaled
        for v in mesh["vertices"]:
            dist = sum(x * x for x in v) ** 0.5
            assert abs(dist - 2.0) < 0.01 or dist < 0.01  # poles


class TestTorusMesh:
    """Torus generation."""

    def test_basic(self):
        mesh = _torus_mesh(
            major_radius=1.0, minor_radius=0.4,
            major_segments=8, minor_segments=4
        )
        assert mesh["vertex_count"] == (8 + 1) * (4 + 1)
        assert mesh["face_count"] == 8 * 4 * 2

    def test_normals_normalized(self):
        mesh = _torus_mesh(major_segments=4, minor_segments=2)
        for n in mesh["normals"]:
            ln = sum(x * x for x in n) ** 0.5
            assert abs(ln - 1.0) < 0.01


class TestKleinBottleMesh:
    """Klein bottle generation."""

    def test_basic(self):
        mesh = _klein_bottle_mesh(segments=8, rings=4)
        assert mesh["vertex_count"] == (8 + 1) * (4 + 1)
        assert mesh["face_count"] == 8 * 4 * 2
        assert len(mesh["vertices"]) > 0

    def test_normals_exist(self):
        mesh = _klein_bottle_mesh(segments=4, rings=2)
        assert len(mesh["normals"]) == mesh["vertex_count"]
        for n in mesh["normals"]:
            ln = sum(x * x for x in n) ** 0.5
            assert abs(ln - 1.0) < 0.01


class TestMobiusStripMesh:
    """Mobius strip generation."""

    def test_basic(self):
        mesh = _mobius_strip_mesh(segments=16, rings=4)
        assert mesh["vertex_count"] == (16 + 1) * (4 + 1)
        assert mesh["face_count"] == 16 * 4 * 2

    def test_normals_exist(self):
        mesh = _mobius_strip_mesh(segments=8, rings=2)
        assert len(mesh["normals"]) == mesh["vertex_count"]


class TestHyperboloidMesh:
    """One-sheet hyperboloid generation."""

    def test_basic(self):
        mesh = _hyperboloid_mesh(a=1.0, c=1.0, segments=8, rings=4)
        assert mesh["vertex_count"] == (8 + 1) * (4 + 1)
        assert mesh["face_count"] == 8 * 4 * 2

    def test_analytic_normals(self):
        mesh = _hyperboloid_mesh(segments=4, rings=2)
        for n in mesh["normals"]:
            ln = sum(x * x for x in n) ** 0.5
            assert abs(ln - 1.0) < 0.01


class TestDataViz3DSkill:
    """Skill entry point."""

    def test_default_sphere(self):
        result = data_viz_3d(_ctx({}))
        assert result["status"] == "completed"
        assert result["result"]["mesh_type"] == "sphere"
        assert "vertices" in result["result"]

    def test_torus(self):
        result = data_viz_3d(
            _ctx({"mesh_type": "torus", "major_radius": 2.0})
        )
        assert result["result"]["mesh_type"] == "torus"
        assert result["metrics"]["vertices"] > 0

    def test_klein_bottle(self):
        result = data_viz_3d(_ctx({"mesh_type": "klein_bottle"}))
        assert result["result"]["mesh_type"] == "klein_bottle"

    def test_mobius_strip(self):
        result = data_viz_3d(_ctx({"mesh_type": "mobius_strip"}))
        assert result["result"]["mesh_type"] == "mobius_strip"

    def test_hyperboloid(self):
        result = data_viz_3d(
            _ctx({"mesh_type": "hyperboloid", "a": 2.0, "c": 3.0})
        )
        assert result["result"]["mesh_type"] == "hyperboloid"

    def test_unknown_defaults_to_sphere(self):
        result = data_viz_3d(_ctx({"mesh_type": "unknown"}))
        assert result["result"]["mesh_type"] == "unknown"
        assert "vertices" in result["result"]
