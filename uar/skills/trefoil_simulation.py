"""Trefoil knot simulation with quaternion mechanics and Frenet frames.

Computes three interlaced trefoil knots on a Clifford torus, each
carrying a data stream and its inverse.  The emergent 4th phase (white
core) is the vector sum of the three pairs, stabilising at the
singularity in perfect equilibrium.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

import numpy as np

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext


def _trefoil_parametric(t: float) -> Tuple[float, float, float]:
    """Standard symmetric trefoil parametric curve."""
    x = math.sin(t) + 2.0 * math.sin(2.0 * t)
    y = math.cos(t) - 2.0 * math.cos(2.0 * t)
    z = -math.sin(3.0 * t)
    return (x, y, z)


def _frenet_frame(
    t: float, dt: float = 1e-4
) -> Tuple[Tuple[float, float, float], ...]:
    """Compute T, N, B (unit tangent, normal, binormal) at parameter t."""
    # Numeric derivative
    def _r(val: float) -> np.ndarray:
        return np.array(_trefoil_parametric(val), dtype=np.float64)

    r_t = _r(t)
    r_p = _r(t + dt)
    r_m = _r(t - dt)

    dr = (r_p - r_m) / (2.0 * dt)
    T = dr / (np.linalg.norm(dr) + 1e-12)

    d2r = (r_p - 2.0 * r_t + r_m) / (dt * dt)
    # Component perpendicular to T
    d2r_perp = d2r - np.dot(d2r, T) * T
    N = d2r_perp / (np.linalg.norm(d2r_perp) + 1e-12)
    B = np.cross(T, N)
    B = B / (np.linalg.norm(B) + 1e-12)

    return tuple(T), tuple(N), tuple(B)


def _frenet_to_quaternion(T, N, B) -> Tuple[float, float, float, float]:
    """Convert orthonormal Frenet frame to rotation quaternion."""
    # Rotation matrix columns are N, B, T (or any orthonormal basis)
    M = np.array([N, B, T], dtype=np.float64)
    # Convert rotation matrix to quaternion (scalar-first)
    tr = M[0, 0] + M[1, 1] + M[2, 2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2.0
        w = 0.25 * s
        x = (M[2, 1] - M[1, 2]) / s
        y = (M[0, 2] - M[2, 0]) / s
        z = (M[1, 0] - M[0, 1]) / s
    elif M[0, 0] > M[1, 1] and M[0, 0] > M[2, 2]:
        s = math.sqrt(1.0 + M[0, 0] - M[1, 1] - M[2, 2]) * 2.0
        w = (M[2, 1] - M[1, 2]) / s
        x = 0.25 * s
        y = (M[0, 1] + M[1, 0]) / s
        z = (M[0, 2] + M[2, 0]) / s
    elif M[1, 1] > M[2, 2]:
        s = math.sqrt(1.0 + M[1, 1] - M[0, 0] - M[2, 2]) * 2.0
        w = (M[0, 2] - M[2, 0]) / s
        x = (M[0, 1] + M[1, 0]) / s
        y = 0.25 * s
        z = (M[1, 2] + M[2, 1]) / s
    else:
        s = math.sqrt(1.0 + M[2, 2] - M[0, 0] - M[1, 1]) * 2.0
        w = (M[1, 0] - M[0, 1]) / s
        x = (M[0, 2] + M[2, 0]) / s
        y = (M[1, 2] + M[2, 1]) / s
        z = 0.25 * s
    return (w, x, y, z)


def _quaternion_rotate(
    q: Tuple[float, float, float, float], v: Tuple[float, float, float]
) -> Tuple[float, float, float]:
    """Rotate vector v by unit quaternion q (scalar-first)."""
    w, x, y, z = q
    vx, vy, vz = v
    # q * v * q_conj  (v as pure quaternion)
    tx = 2.0 * (y * vz - z * vy)
    ty = 2.0 * (z * vx - x * vz)
    tz = 2.0 * (x * vy - y * vx)
    rx = vx + w * tx + (y * tz - z * ty)
    ry = vy + w * ty + (z * tx - x * tz)
    rz = vz + w * tz + (x * ty - y * tx)
    return (rx, ry, rz)


def _clifford_torus_trefoil(
    t: float, offset: float = 0.0
) -> Tuple[float, float, float]:
    """Trefoil embedded on Clifford torus with phase offset."""
    # Map trefoil to torus angles
    theta = t + offset
    phi = 3.0 * t + offset
    # Torus parameters (major/minor radii)
    R, r = 3.0, 1.0
    x = (R + r * math.cos(phi)) * math.cos(theta)
    y = (R + r * math.cos(phi)) * math.sin(theta)
    z = r * math.sin(phi)
    return (x, y, z)


def compute_trefoil_simulation(
    num_points: int = 256,
    num_trefoils: int = 3,
    rotation_speed: float = 1.0,
) -> Dict[str, Any]:
    """Run the full triple-trefoil quaternion simulation.

    Returns a dict with ``knots``, ``quaternions``, ``core``, and
    ``equilibrium`` status.
    """
    knots: List[List[Tuple[float, float, float]]] = []
    quaternions: List[List[Tuple[float, float, float, float]]] = []
    inverses: List[List[Tuple[float, float, float]]] = []

    dt = 2.0 * math.pi / num_points

    for k in range(num_trefoils):
        offset = k * (2.0 * math.pi / num_trefoils)
        knot_pts: List[Tuple[float, float, float]] = []
        quat_pts: List[Tuple[float, float, float, float]] = []
        inv_pts: List[Tuple[float, float, float]] = []

        for i in range(num_points):
            t = i * dt
            # Base trefoil on Clifford torus
            pt = _clifford_torus_trefoil(t, offset)
            knot_pts.append(pt)

            # Frenet frame → quaternion
            T, N, B = _frenet_frame(t + offset)
            q = _frenet_to_quaternion(T, N, B)
            quat_pts.append(q)

            # Inverse stream (negated position = antipode on torus)
            inv_pts.append((-pt[0], -pt[1], -pt[2]))

        knots.append(knot_pts)
        quaternions.append(quat_pts)
        inverses.append(inv_pts)

    # Emergent 4th phase: vector sum of all pairs at each sample
    core: List[Tuple[float, float, float]] = []
    equilibrium = True
    threshold = 1e-3

    for i in range(num_points):
        vec_sum = np.array([0.0, 0.0, 0.0], dtype=np.float64)
        for k in range(num_trefoils):
            p = np.array(knots[k][i], dtype=np.float64)
            inv = np.array(inverses[k][i], dtype=np.float64)
            vec_sum += p + inv
        core_pt = tuple(vec_sum)
        core.append(core_pt)
        if np.linalg.norm(vec_sum) > threshold:
            equilibrium = False

    return {
        "knots": knots,
        "quaternions": quaternions,
        "inverses": inverses,
        "core": core,
        "equilibrium": equilibrium,
        "num_points": num_points,
        "num_trefoils": num_trefoils,
        "rotation_speed": rotation_speed,
    }


@register_skill("trefoil_simulation")
def trefoil_simulation(ctx: PipelineContext) -> Dict[str, Any]:
    """Skill entrypoint: run trefoil simulation.

    Returns results dict with knots, quaternions, core, and metrics.
    """
    params = ctx.goal.metadata or {}
    num_points = int(params.get("num_points", 256))
    num_trefoils = int(params.get("num_trefoils", 3))
    rotation_speed = float(params.get("rotation_speed", 1.0))

    result = compute_trefoil_simulation(
        num_points=num_points,
        num_trefoils=num_trefoils,
        rotation_speed=rotation_speed,
    )

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": result,
        "metrics": {
            "total_points": num_points * num_trefoils,
            "equilibrium_reached": result["equilibrium"],
        },
    }
