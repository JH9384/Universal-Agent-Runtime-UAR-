"""Binary streaming utilities for large simulation datasets.

Supports efficient serialization of 3D point clouds, quaternions,
and mesh data for WebSocket binary frame transmission.
"""

from __future__ import annotations

import struct
from typing import Any, Dict, List, Tuple


def pack_floats(values: List[float]) -> bytes:
    """Pack a list of floats into binary (IEEE 754 double)."""
    return struct.pack(f"<{len(values)}d", *values)


def unpack_floats(data: bytes) -> Tuple[float, ...]:
    """Unpack binary into floats."""
    count = len(data) // 8
    return struct.unpack(f"<{count}d", data)


def pack_points(
    points: List[Tuple[float, float, float]],
) -> bytes:
    """Pack 3D points as flat binary: [x,y,z, x,y,z, ...]."""
    flat = [c for pt in points for c in pt]
    return pack_floats(flat)


def pack_quaternions(
    quats: List[Tuple[float, float, float, float]],
) -> bytes:
    """Pack quaternions as flat binary: [w,x,y,z, ...]."""
    flat = [c for q in quats for c in q]
    return pack_floats(flat)


def serialize_trefoil(data: Dict[str, Any]) -> Dict[str, bytes]:
    """Serialize trefoil simulation data into binary chunks.

    Returns a dict mapping chunk names to binary payloads.
    """
    chunks: Dict[str, bytes] = {}

    # Pack each knot as a binary chunk
    for i, knot in enumerate(data.get("knots", [])):
        chunks[f"knot_{i}"] = pack_points(knot)

    # Pack core
    core = data.get("core", [])
    if core:
        chunks["core"] = pack_points(core)

    # Pack metadata as a small binary header
    meta = struct.pack(
        "<4i4d",
        data.get("num_points", 0),
        data.get("num_trefoils", 0),
        len(data.get("keyframes", [])),
        1 if data.get("equilibrium") else 0,
        data.get("expansion", 1.0),
        data.get("torsional_sync", 0.0),
        data.get("twistor_strength", 0.0),
        data.get("phase_lock_strength", 0.0),
    )
    chunks["meta"] = meta

    return chunks


def serialize_molecular(data: Dict[str, Any]) -> Dict[str, bytes]:
    """Serialize molecular structure into binary chunks."""
    chunks: Dict[str, bytes] = {}

    atoms = data.get("atoms", [])
    if atoms:
        flat = []
        for a in atoms:
            flat.extend([a.get("x", 0.0), a.get("y", 0.0), a.get("z", 0.0)])
            flat.append(a.get("radius", 0.5))
        chunks["atoms"] = pack_floats(flat)

    bonds = data.get("bonds", [])
    if bonds:
        # Pack as int pairs + float distance
        flat_bonds = []
        for b in bonds:
            flat_bonds.extend([float(b[0]), float(b[1]), b[2]])
        chunks["bonds"] = pack_floats(flat_bonds)

    meta = struct.pack(
        "<2i",
        data.get("atom_count", 0),
        data.get("bond_count", 0),
    )
    chunks["meta"] = meta

    return chunks


def serialize_quantum_circuit(data: Dict[str, Any]) -> Dict[str, bytes]:
    """Serialize quantum circuit layout into binary chunks."""
    chunks: Dict[str, bytes] = {}

    tracks = data.get("qubit_tracks", [])
    if tracks:
        flat = [c for t in tracks for c in t]
        chunks["tracks"] = pack_floats(flat)

    gates = data.get("gates", [])
    if gates:
        flat = []
        for g in gates:
            flat.extend(g.get("position", [0.0, 0.0, 0.0]))
            flat.append(g.get("size", 0.4))
        chunks["gates"] = pack_floats(flat)

    meta = struct.pack(
        "<3i",
        data.get("qubits", 0),
        data.get("depth", 0),
        data.get("gate_count", 0),
    )
    chunks["meta"] = meta

    return chunks
