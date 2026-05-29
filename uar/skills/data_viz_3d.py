"""3D data visualization skill.

Generates 3D mesh data (vertices, faces, normals) for parametric
surfaces that can be rendered by the frontend using React Three Fiber.
Pure Python — no VTK/PyVista required.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import skill_guard


def _sphere_mesh(
    radius: float = 1.0, segments: int = 32, rings: int = 16
) -> Dict[str, Any]:
    """Generate UV sphere vertices and face indices."""
    vertices: List[List[float]] = []
    normals: List[List[float]] = []
    uvs: List[List[float]] = []
    indices: List[int] = []

    for ring in range(rings + 1):
        phi = math.pi * ring / rings
        for seg in range(segments + 1):
            theta = 2 * math.pi * seg / segments
            x = radius * math.sin(phi) * math.cos(theta)
            y = radius * math.cos(phi)
            z = radius * math.sin(phi) * math.sin(theta)
            vertices.append([x, y, z])
            normals.append([x / radius, y / radius, z / radius])
            uvs.append([seg / segments, ring / rings])

    for ring in range(rings):
        for seg in range(segments):
            a = ring * (segments + 1) + seg
            b = a + segments + 1
            indices.extend([a, b, a + 1])
            indices.extend([b, b + 1, a + 1])

    return {
        "vertices": vertices,
        "normals": normals,
        "uvs": uvs,
        "indices": indices,
        "vertex_count": len(vertices),
        "face_count": len(indices) // 3,
    }


def _torus_mesh(
    major_radius: float = 1.0,
    minor_radius: float = 0.4,
    major_segments: int = 32,
    minor_segments: int = 16,
) -> Dict[str, Any]:
    """Generate torus vertices and face indices."""
    vertices: List[List[float]] = []
    normals: List[List[float]] = []
    uvs: List[List[float]] = []
    indices: List[int] = []

    for i in range(major_segments + 1):
        u = 2 * math.pi * i / major_segments
        for j in range(minor_segments + 1):
            v = 2 * math.pi * j / minor_segments
            x = (major_radius + minor_radius * math.cos(v)) * math.cos(u)
            y = minor_radius * math.sin(v)
            z = (major_radius + minor_radius * math.cos(v)) * math.sin(u)

            # Normal
            nx = math.cos(v) * math.cos(u)
            ny = math.sin(v)
            nz = math.cos(v) * math.sin(u)
            len_n = math.sqrt(nx * nx + ny * ny + nz * nz)

            vertices.append([x, y, z])
            normals.append([nx / len_n, ny / len_n, nz / len_n])
            uvs.append([i / major_segments, j / minor_segments])

    for i in range(major_segments):
        for j in range(minor_segments):
            a = i * (minor_segments + 1) + j
            b = a + minor_segments + 1
            indices.extend([a, b, a + 1])
            indices.extend([b, b + 1, a + 1])

    return {
        "vertices": vertices,
        "normals": normals,
        "uvs": uvs,
        "indices": indices,
        "vertex_count": len(vertices),
        "face_count": len(indices) // 3,
    }


def _klein_bottle_mesh(
    segments: int = 32, rings: int = 16
) -> Dict[str, Any]:
    """Generate Klein bottle vertices and face indices."""
    vertices: List[List[float]] = []
    normals: List[List[float]] = []
    uvs: List[List[float]] = []
    indices: List[int] = []

    for ring in range(rings + 1):
        v = math.pi * 2 * ring / rings
        for seg in range(segments + 1):
            u = 2 * math.pi * seg / segments
            # Parametric Klein bottle (figure-8 immersion)
            a = 2  # scale factor
            cu2 = math.cos(u / 2)
            su2 = math.sin(u / 2)
            sv = math.sin(v)
            s2v = math.sin(2 * v)
            x = (a + cu2 * sv - su2 * s2v) * math.cos(u)
            y = (a + cu2 * sv - su2 * s2v) * math.sin(u)
            z = su2 * sv + cu2 * s2v
            vertices.append([x, y, z])
            # Approximate normal via cross product of partial derivatives
            du = 0.001
            dv = 0.001
            u1, v1 = u + du, v
            cu1 = math.cos(u1 / 2)
            su1 = math.sin(u1 / 2)
            sv1 = math.sin(v1)
            s2v1 = math.sin(2 * v1)
            x1 = (a + cu1 * sv1 - su1 * s2v1) * math.cos(u1)
            y1 = (a + cu1 * sv1 - su1 * s2v1) * math.sin(u1)
            z1 = su1 * sv1 + cu1 * s2v1
            u2, v2 = u, v + dv
            cu2b = math.cos(u2 / 2)
            su2b = math.sin(u2 / 2)
            sv2 = math.sin(v2)
            s2v2 = math.sin(2 * v2)
            x2 = (a + cu2b * sv2 - su2b * s2v2) * math.cos(u2)
            y2 = (a + cu2b * sv2 - su2b * s2v2) * math.sin(u2)
            z2 = su2b * sv2 + cu2b * s2v2
            tx = [x1 - x, y1 - y, z1 - z]
            ty = [x2 - x, y2 - y, z2 - z]
            nx = ty[1] * tx[2] - ty[2] * tx[1]
            ny = ty[2] * tx[0] - ty[0] * tx[2]
            nz = ty[0] * tx[1] - ty[1] * tx[0]
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
            normals.append([nx / ln, ny / ln, nz / ln])
            uvs.append([seg / segments, ring / rings])

    for ring in range(rings):
        for seg in range(segments):
            a = ring * (segments + 1) + seg
            b = a + segments + 1
            indices.extend([a, b, a + 1])
            indices.extend([b, b + 1, a + 1])

    return {
        "vertices": vertices,
        "normals": normals,
        "uvs": uvs,
        "indices": indices,
        "vertex_count": len(vertices),
        "face_count": len(indices) // 3,
    }


def _mobius_strip_mesh(
    segments: int = 64, rings: int = 8
) -> Dict[str, Any]:
    """Generate Mobius strip vertices and face indices."""
    vertices: List[List[float]] = []
    normals: List[List[float]] = []
    uvs: List[List[float]] = []
    indices: List[int] = []

    width = 0.3
    for ring in range(rings + 1):
        t = 2 * math.pi * ring / rings
        for seg in range(segments + 1):
            s = -width + 2 * width * seg / segments
            x = (1 + s * math.cos(t / 2)) * math.cos(t)
            y = (1 + s * math.cos(t / 2)) * math.sin(t)
            z = s * math.sin(t / 2)
            vertices.append([x, y, z])
            # Approximate normal
            dt = 0.001
            ds = 0.001
            t1, s1 = t + dt, s
            x1 = (1 + s1 * math.cos(t1 / 2)) * math.cos(t1)
            y1 = (1 + s1 * math.cos(t1 / 2)) * math.sin(t1)
            z1 = s1 * math.sin(t1 / 2)
            t2, s2 = t, s + ds
            x2 = (1 + s2 * math.cos(t2 / 2)) * math.cos(t2)
            y2 = (1 + s2 * math.cos(t2 / 2)) * math.sin(t2)
            z2 = s2 * math.sin(t2 / 2)
            tx = [x1 - x, y1 - y, z1 - z]
            ty = [x2 - x, y2 - y, z2 - z]
            nx = ty[1] * tx[2] - ty[2] * tx[1]
            ny = ty[2] * tx[0] - ty[0] * tx[2]
            nz = ty[0] * tx[1] - ty[1] * tx[0]
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
            normals.append([nx / ln, ny / ln, nz / ln])
            uvs.append([seg / segments, ring / rings])

    for ring in range(rings):
        for seg in range(segments):
            a = ring * (segments + 1) + seg
            b = a + segments + 1
            indices.extend([a, b, a + 1])
            indices.extend([b, b + 1, a + 1])

    return {
        "vertices": vertices,
        "normals": normals,
        "uvs": uvs,
        "indices": indices,
        "vertex_count": len(vertices),
        "face_count": len(indices) // 3,
    }


def _hyperboloid_mesh(
    a: float = 1.0, c: float = 1.0,
    segments: int = 32, rings: int = 16
) -> Dict[str, Any]:
    """Generate one-sheet hyperboloid vertices and face indices."""
    vertices: List[List[float]] = []
    normals: List[List[float]] = []
    uvs: List[List[float]] = []
    indices: List[int] = []

    for ring in range(rings + 1):
        v = -2 + 4 * ring / rings
        for seg in range(segments + 1):
            u = 2 * math.pi * seg / segments
            # One-sheet hyperboloid: x = a*cosh(v)*cos(u), etc.
            cosh_v = math.cosh(v)
            sinh_v = math.sinh(v)
            x = a * cosh_v * math.cos(u)
            y = a * cosh_v * math.sin(u)
            z = c * sinh_v
            vertices.append([x, y, z])
            # Analytic normal
            nx = math.cosh(v) * math.cos(u) / a
            ny = math.cosh(v) * math.sin(u) / a
            nz = -sinh_v / c
            ln = math.sqrt(nx * nx + ny * ny + nz * nz) or 1
            normals.append([nx / ln, ny / ln, nz / ln])
            uvs.append([seg / segments, ring / rings])

    for ring in range(rings):
        for seg in range(segments):
            a_idx = ring * (segments + 1) + seg
            b = a_idx + segments + 1
            indices.extend([a_idx, b, a_idx + 1])
            indices.extend([b, b + 1, a_idx + 1])

    return {
        "vertices": vertices,
        "normals": normals,
        "uvs": uvs,
        "indices": indices,
        "vertex_count": len(vertices),
        "face_count": len(indices) // 3,
    }


@register_skill("data_viz_3d")
@skill_guard("Data viz 3d")
def data_viz_3d(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate 3D mesh data for parametric surfaces.

    Parameters (from ctx.goal.metadata):
        mesh_type: str - 'sphere', 'torus', 'klein_bottle',
                         'mobius_strip', 'hyperboloid' (default: sphere)
        radius: float - For sphere (default: 1.0)
        major_radius: float - For torus (default: 1.0)
        minor_radius: float - For torus (default: 0.4)
    """
    params = ctx.goal.metadata or {}
    mesh_type = str(params.get("mesh_type", "sphere")).lower()

    mesh_generators = {
        "torus": lambda: _torus_mesh(
            major_radius=float(params.get("major_radius", 1.0)),
            minor_radius=float(params.get("minor_radius", 0.4)),
        ),
        "klein_bottle": _klein_bottle_mesh,
        "mobius_strip": _mobius_strip_mesh,
        "hyperboloid": lambda: _hyperboloid_mesh(
            a=float(params.get("a", 1.0)),
            c=float(params.get("c", 1.0)),
        ),
    }

    if mesh_type in mesh_generators:
        mesh = mesh_generators[mesh_type]()
    else:
        mesh = _sphere_mesh(
            radius=float(params.get("radius", 1.0)),
        )

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "mesh_type": mesh_type,
            **mesh,
        },
        "metrics": {
            "vertices": mesh["vertex_count"],
            "faces": mesh["face_count"],
        },
    }



