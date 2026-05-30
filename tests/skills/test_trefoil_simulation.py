"""Tests for uar.skills.trefoil_simulation."""

import math

import numpy as np
import pytest

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.trefoil_simulation import (
    _clifford_torus_expanded,
    _clifford_torus_trefoil,
    _frenet_frame,
    _frenet_to_quaternion,
    _phase_lock,
    _quaternion_rotate,
    _slerp,
    _torsion_sync,
    _trefoil_parametric,
    _twistor_transform,
    compute_trefoil_simulation,
    trefoil_simulation,
)


class TestTrefoilParametric:
    def test_basic(self):
        x, y, z = _trefoil_parametric(0.0)
        assert isinstance(x, float)
        assert isinstance(y, float)
        assert isinstance(z, float)


class TestFrenetFrame:
    def test_basic(self):
        T, N, B = _frenet_frame(0.0)
        assert len(T) == 3
        assert len(N) == 3
        assert len(B) == 3
        # T, N, B should be unit vectors
        assert abs(np.linalg.norm(T) - 1.0) < 1e-6
        assert abs(np.linalg.norm(N) - 1.0) < 1e-6
        assert abs(np.linalg.norm(B) - 1.0) < 1e-6


class TestFrenetToQuaternion:
    def test_tr_positive(self):
        T = (1.0, 0.0, 0.0)
        N = (0.0, 1.0, 0.0)
        B = (0.0, 0.0, 1.0)
        q = _frenet_to_quaternion(T, N, B)
        assert len(q) == 4

    def test_m00_dominant(self):
        # Rotation matrix where M[0,0] is largest
        T = (0.0, 0.0, 1.0)
        N = (1.0, 0.0, 0.0)
        B = (0.0, 1.0, 0.0)
        q = _frenet_to_quaternion(T, N, B)
        assert len(q) == 4

    def test_m11_dominant(self):
        T = (0.0, 1.0, 0.0)
        N = (0.0, 0.0, 1.0)
        B = (1.0, 0.0, 0.0)
        q = _frenet_to_quaternion(T, N, B)
        assert len(q) == 4

    def test_else_branch(self):
        T = (0.0, 0.0, 1.0)
        N = (0.0, 1.0, 0.0)
        B = (1.0, 0.0, 0.0)
        q = _frenet_to_quaternion(T, N, B)
        assert len(q) == 4


class TestQuaternionRotate:
    def test_basic(self):
        q = (1.0, 0.0, 0.0, 0.0)  # identity
        v = (1.0, 0.0, 0.0)
        result = _quaternion_rotate(q, v)
        assert len(result) == 3


class TestCliffordTorus:
    def test_basic(self):
        x, y, z = _clifford_torus_trefoil(0.0)
        assert isinstance(x, float)

    def test_with_offset(self):
        x, y, z = _clifford_torus_trefoil(0.0, offset=1.0)
        assert isinstance(x, float)


class TestSlerp:
    def test_basic(self):
        q1 = (1.0, 0.0, 0.0, 0.0)
        q2 = (0.0, 1.0, 0.0, 0.0)
        result = _slerp(q1, q2, 0.5)
        assert len(result) == 4

    def test_shortest_path(self):
        q1 = (1.0, 0.0, 0.0, 0.0)
        q2 = (-1.0, 0.0, 0.0, 0.0)
        result = _slerp(q1, q2, 0.5)
        assert len(result) == 4

    def test_theta_near_zero(self):
        q1 = (1.0, 0.0, 0.0, 0.0)
        q2 = (1.0, 0.0, 0.0, 0.0)
        result = _slerp(q1, q2, 0.5)
        assert len(result) == 4


class TestTwistorTransform:
    def test_zero_strength(self):
        pt = (1.0, 0.0, 0.0)
        result = _twistor_transform(pt, 0.0, 0.0)
        assert len(result) == 3
        assert result == pytest.approx(pt, abs=1e-10)

    def test_nonzero_strength(self):
        pt = (1.0, 0.0, 0.0)
        result = _twistor_transform(pt, 1.0, math.pi / 2)
        assert len(result) == 3


class TestTorsionSync:
    def test_free(self):
        result = _torsion_sync(0.0, 0, 3, 0.0)
        assert isinstance(result, float)

    def test_locked(self):
        result = _torsion_sync(1.0, 1, 3, 1.0)
        assert result == pytest.approx(1.0, abs=1e-10)


class TestPhaseLock:
    def test_free(self):
        result = _phase_lock(1.0, "free", 0.5, 0)
        assert result == 1.0

    def test_locked(self):
        result = _phase_lock(1.0, "locked", 1.0, 1)
        assert isinstance(result, float)

    def test_anti(self):
        result = _phase_lock(1.0, "anti", 1.0, 1)
        assert isinstance(result, float)

    def test_unknown_mode(self):
        result = _phase_lock(1.0, "unknown", 1.0, 0)
        assert result == 1.0


class TestCliffordTorusExpanded:
    def test_basic(self):
        x, y, z = _clifford_torus_expanded(0.0, 0.0, 1.0)
        assert isinstance(x, float)


class TestComputeTrefoilSimulation:
    def test_defaults(self):
        result = compute_trefoil_simulation()
        assert "knots" in result
        assert "quaternions" in result
        assert "core" in result
        assert "equilibrium" in result
        assert "keyframes" in result
        assert len(result["knots"]) == 3

    def test_no_keyframes(self):
        result = compute_trefoil_simulation(
            generate_keyframes=False, num_keyframes=0
        )
        assert len(result["keyframes"]) == 0

    def test_with_twistor(self):
        result = compute_trefoil_simulation(
            twistor_strength=1.0,
            generate_keyframes=False,
        )
        assert len(result["knots"]) == 3

    def test_torsion_sync(self):
        result = compute_trefoil_simulation(
            torsional_sync=1.0,
            generate_keyframes=False,
        )
        assert len(result["knots"]) == 3

    def test_phase_lock(self):
        result = compute_trefoil_simulation(
            phase_lock_mode="locked",
            phase_lock_strength=1.0,
            generate_keyframes=False,
        )
        assert len(result["knots"]) == 3

    def test_small_params(self):
        result = compute_trefoil_simulation(
            num_points=8,
            num_trefoils=2,
            generate_keyframes=True,
            num_keyframes=2,
        )
        assert len(result["knots"]) == 2
        assert len(result["knots"][0]) == 8


class TestTrefoilSimulationSkill:
    def test_default_params(self):
        ctx = PipelineContext(
            goal=GoalSpec(
                id="t", user_intent="t", objective="t", metadata={}
            )
        )
        result = trefoil_simulation(ctx)
        assert result["status"] == "completed"
        assert "result" in result
        assert "metrics" in result

    def test_custom_params(self):
        ctx = PipelineContext(
            goal=GoalSpec(
                id="t",
                user_intent="t",
                objective="t",
                metadata={
                    "num_points": 16,
                    "num_trefoils": 2,
                    "twistor_strength": 0.5,
                    "phase_lock_mode": "anti",
                    "generate_keyframes": False,
                },
            )
        )
        result = trefoil_simulation(ctx)
        assert result["status"] == "completed"
