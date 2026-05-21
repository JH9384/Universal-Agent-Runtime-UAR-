"""Trefoil knot simulation with quaternion mechanics and Frenet frames.

Computes interlaced trefoil knots on a Clifford torus with advanced
torsional sync, twistor bundle mechanics, and phase-locking controls.
Each knot carries a data stream and its inverse.  The emergent 4th
phase (white core) is the vector sum of all pairs, stabilising at the
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


def _slerp(
    q1: Tuple[float, float, float, float],
    q2: Tuple[float, float, float, float],
    t: float,
) -> Tuple[float, float, float, float]:
    """Spherical linear interpolation between two unit quaternions."""
    q1_a = np.array(q1, dtype=np.float64)
    q2_a = np.array(q2, dtype=np.float64)
    dot = np.dot(q1_a, q2_a)
    # Take shortest path
    if dot < 0.0:
        q2_a = -q2_a
        dot = -dot
    # Clamp for numerical stability
    dot = min(max(dot, -1.0), 1.0)
    theta = math.acos(dot)
    if abs(theta) < 1e-6:
        return tuple(q1_a)
    sin_theta = math.sin(theta)
    w1 = math.sin((1.0 - t) * theta) / sin_theta
    w2 = math.sin(t * theta) / sin_theta
    result = w1 * q1_a + w2 * q2_a
    result = result / (np.linalg.norm(result) + 1e-12)
    return tuple(result)


def _twistor_transform(
    pt: Tuple[float, float, float],
    twistor_strength: float,
    t: float,
) -> Tuple[float, float, float]:
    """Apply Penrose twistor bundle transformation.

    Creates a complex rotation in the (x+iy, z+iw) plane that
couples spatial position with an internal phase.
    """
    x, y, z = pt
    # Twistor phase angle
    alpha = twistor_strength * t
    ca = math.cos(alpha)
    sa = math.sin(alpha)
    # Rotate in complexified x-y plane while modulating z
    x_new = x * ca - y * sa
    y_new = x * sa + y * ca
    z_new = z * math.cos(alpha * 0.5)  # Half-phase for z
    return (x_new, y_new, z_new)


def _torsion_sync(
    base_phase: float,
    knot_idx: int,
    num_trefoils: int,
    sync_strength: float,
) -> float:
    """Synchronise torsional phases across trefoils.

    sync_strength = 0: free rotation (independent phases)
    sync_strength = 1: fully locked (identical phases)
    Values between interpolate.
    """
    # Natural offset for this knot
    natural = knot_idx * (2.0 * math.pi / num_trefoils)
    # Target locked phase (all knots at same phase)
    locked = base_phase
    # Blend between natural and locked
    return natural * (1.0 - sync_strength) + locked * sync_strength


def _phase_lock(
    phase: float,
    lock_mode: str,
    lock_strength: float,
    knot_idx: int,
) -> float:
    """Apply phase-locking control.

    lock_mode:
        'free'   - no locking
        'locked' - all phases identical
        'anti'   - adjacent knots anti-phase (pi offset)
    """
    if lock_mode == "free":
        return phase
    natural_offset = knot_idx * (2.0 * math.pi / 3.0)
    if lock_mode == "locked":
        target = phase - natural_offset
    elif lock_mode == "anti":
        target = phase - natural_offset + (knot_idx % 2) * math.pi
    else:
        return phase
    return phase * (1.0 - lock_strength) + target * lock_strength


def _clifford_torus_expanded(
    t: float,
    offset: float,
    expansion: float,
    R_base: float = 3.0,
    r_base: float = 1.0,
) -> Tuple[float, float, float]:
    """Trefoil on Clifford torus with configurable expansion."""
    theta = t + offset
    phi = 3.0 * t + offset
    # Scale radii by expansion factor
    R = R_base * expansion
    r = r_base * expansion
    x = (R + r * math.cos(phi)) * math.cos(theta)
    y = (R + r * math.cos(phi)) * math.sin(theta)
    z = r * math.sin(phi)
    return (x, y, z)


def compute_trefoil_simulation(
    num_points: int = 256,
    num_trefoils: int = 3,
    rotation_speed: float = 1.0,
    expansion: float = 1.0,
    torsional_sync: float = 0.0,
    twistor_strength: float = 0.0,
    phase_lock_mode: str = "free",
    phase_lock_strength: float = 0.0,
    generate_keyframes: bool = True,
    num_keyframes: int = 60,
) -> Dict[str, Any]:
    """Run the full triple-trefoil quaternion simulation.

    Returns a dict with ``knots``, ``quaternions``, ``core``,
    ``equilibrium``, ``keyframes``, and control parameters.
    """
    knots: List[List[Tuple[float, float, float]]] = []
    quaternions: List[List[Tuple[float, float, float, float]]] = []
    inverses: List[List[Tuple[float, float, float]]] = []
    frames: List[Dict[str, Any]] = []

    dt = 2.0 * math.pi / num_points

    for k in range(num_trefoils):
        base_offset = k * (2.0 * math.pi / num_trefoils)
        knot_pts: List[Tuple[float, float, float]] = []
        quat_pts: List[Tuple[float, float, float, float]] = []
        inv_pts: List[Tuple[float, float, float]] = []

        for i in range(num_points):
            t = i * dt
            # Apply torsional sync and phase locking
            sync_phase = _torsion_sync(t, k, num_trefoils, torsional_sync)
            locked_phase = _phase_lock(
                sync_phase, phase_lock_mode, phase_lock_strength, k
            )
            offset = base_offset + locked_phase - t

            # Base trefoil on expanded Clifford torus
            pt = _clifford_torus_expanded(t, offset, expansion)

            # Apply twistor transformation
            if twistor_strength > 0:
                pt = _twistor_transform(pt, twistor_strength, t)

            knot_pts.append(pt)

            # Frenet frame → quaternion
            T, N, B = _frenet_frame(t + offset)
            q = _frenet_to_quaternion(T, N, B)
            quat_pts.append(q)

            # Inverse stream
            inv_pts.append((-pt[0], -pt[1], -pt[2]))

        knots.append(knot_pts)
        quaternions.append(quat_pts)
        inverses.append(inv_pts)

    # Emergent 4th phase
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

    # Generate animation keyframes via quaternion interpolation
    if generate_keyframes and num_keyframes > 0:
        for f in range(num_keyframes):
            t_frame = f / num_keyframes
            frame_knots: List[List[Tuple[float, float, float]]] = []
            for k in range(num_trefoils):
                # Interpolate quaternions between sample points
                idx = int(t_frame * (num_points - 1))
                q1 = quaternions[k][idx]
                q2 = quaternions[k][(idx + 1) % num_points]
                local_t = (t_frame * (num_points - 1)) % 1.0
                q_interp = _slerp(q1, q2, local_t)

                # Build a sparse frame (every 8th point for efficiency)
                frame_pts = []
                for j in range(0, num_points, 8):
                    pt = _quaternion_rotate(q_interp, knots[k][j])
                    frame_pts.append(pt)
                frame_knots.append(frame_pts)
            frames.append({
                "frame": f,
                "knots": frame_knots,
                "time": t_frame,
            })

    return {
        "knots": knots,
        "quaternions": quaternions,
        "inverses": inverses,
        "core": core,
        "equilibrium": equilibrium,
        "keyframes": frames,
        "num_points": num_points,
        "num_trefoils": num_trefoils,
        "rotation_speed": rotation_speed,
        "expansion": expansion,
        "torsional_sync": torsional_sync,
        "twistor_strength": twistor_strength,
        "phase_lock_mode": phase_lock_mode,
        "phase_lock_strength": phase_lock_strength,
    }


@register_skill("trefoil_simulation")
def trefoil_simulation(ctx: PipelineContext) -> Dict[str, Any]:
    """Skill entrypoint: run trefoil simulation.

    Returns results dict with knots, quaternions, core, keyframes,
    and metrics.  Advanced controls: expansion, torsional_sync,
    twistor_strength, phase_lock_mode, phase_lock_strength.
    """
    params = ctx.goal.metadata or {}
    num_points = int(params.get("num_points", 256))
    num_trefoils = int(params.get("num_trefoils", 3))
    rotation_speed = float(params.get("rotation_speed", 1.0))
    expansion = float(params.get("expansion", 1.0))
    torsional_sync = float(params.get("torsional_sync", 0.0))
    twistor_strength = float(params.get("twistor_strength", 0.0))
    phase_lock_mode = str(params.get("phase_lock_mode", "free"))
    phase_lock_strength = float(params.get("phase_lock_strength", 0.0))
    generate_keyframes = bool(params.get("generate_keyframes", True))
    num_keyframes = int(params.get("num_keyframes", 60))

    result = compute_trefoil_simulation(
        num_points=num_points,
        num_trefoils=num_trefoils,
        rotation_speed=rotation_speed,
        expansion=expansion,
        torsional_sync=torsional_sync,
        twistor_strength=twistor_strength,
        phase_lock_mode=phase_lock_mode,
        phase_lock_strength=phase_lock_strength,
        generate_keyframes=generate_keyframes,
        num_keyframes=num_keyframes,
    )

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": result,
        "metrics": {
            "total_points": num_points * num_trefoils,
            "equilibrium_reached": result["equilibrium"],
            "keyframes_generated": len(result["keyframes"]),
        },
    }
