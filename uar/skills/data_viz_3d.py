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


def data_viz_3d(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate 3D mesh data for parametric surfaces.

    Parameters (from ctx.goal.metadata):
        mesh_type: str - 'sphere' or 'torus' (default: sphere)
        radius: float - For sphere (default: 1.0)
        major_radius: float - For torus (default: 1.0)
        minor_radius: float - For torus (default: 0.4)
    """
    params = ctx.goal.metadata or {}
    mesh_type = str(params.get("mesh_type", "sphere")).lower()

    if mesh_type == "torus":
        mesh = _torus_mesh(
            major_radius=float(params.get("major_radius", 1.0)),
            minor_radius=float(params.get("minor_radius", 0.4)),
        )
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


register_skill("data_viz_3d")(data_viz_3d)
