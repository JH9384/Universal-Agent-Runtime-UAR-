"""Tests for binary_stream serialization utilities.

Covers float packing, 3D points, quaternions, and domain-specific
serializers (trefoil, molecular, quantum circuit).
"""

import struct

import pytest

from uar.core.binary_stream import (
    pack_floats,
    unpack_floats,
    pack_points,
    pack_quaternions,
    serialize_trefoil,
    serialize_molecular,
    serialize_quantum_circuit,
)


class TestPackFloats:
    """Basic float serialization roundtrip."""

    def test_roundtrip_single(self):
        original = [3.14159]
        packed = pack_floats(original)
        assert len(packed) == 8  # one double
        unpacked = unpack_floats(packed)
        assert pytest.approx(unpacked[0]) == 3.14159

    def test_roundtrip_multiple(self):
        original = [1.0, 2.0, -0.5, 1e10]
        packed = pack_floats(original)
        assert len(packed) == 32
        unpacked = unpack_floats(packed)
        for a, b in zip(original, unpacked):
            assert pytest.approx(a) == b

    def test_empty_list(self):
        packed = pack_floats([])
        assert packed == b""
        unpacked = unpack_floats(packed)
        assert unpacked == ()

    def test_unpack_truncated(self):
        """Unpack handles bytes not aligned to 8."""
        packed = b"\x00\x00\x00\x00\x00\x00\xf0?"  # 9 bytes
        count = len(packed) // 8
        assert count == 1
        unpacked = unpack_floats(packed)
        assert len(unpacked) == 1


class TestPackPoints:
    """3D point cloud packing."""

    def test_three_points(self):
        points = [(1.0, 2.0, 3.0), (4.0, 5.0, 6.0)]
        packed = pack_points(points)
        assert len(packed) == 48  # 6 doubles * 8 bytes
        unpacked = unpack_floats(packed)
        assert pytest.approx(unpacked[0]) == 1.0
        assert pytest.approx(unpacked[5]) == 6.0

    def test_empty_points(self):
        assert pack_points([]) == b""


class TestPackQuaternions:
    """Quaternion [w,x,y,z] packing."""

    def test_single_quaternion(self):
        quats = [(0.5, 0.5, 0.5, 0.5)]
        packed = pack_quaternions(quats)
        assert len(packed) == 32
        unpacked = unpack_floats(packed)
        assert pytest.approx(unpacked[0]) == 0.5
        assert pytest.approx(unpacked[3]) == 0.5

    def test_empty_quaternions(self):
        assert pack_quaternions([]) == b""


class TestSerializeTrefoil:
    """Trefoil simulation data serialization."""

    def test_basic(self):
        data = {
            "knots": [
                [(0.0, 0.0, 0.0), (1.0, 1.0, 1.0)],
            ],
            "core": [(2.0, 2.0, 2.0)],
            "num_points": 3,
            "num_trefoils": 1,
            "keyframes": [],
            "equilibrium": True,
            "expansion": 1.5,
            "torsional_sync": 0.1,
            "twistor_strength": 0.2,
            "phase_lock_strength": 0.3,
        }
        chunks = serialize_trefoil(data)
        assert "knot_0" in chunks
        assert "core" in chunks
        assert "meta" in chunks
        assert len(chunks["meta"]) == struct.calcsize("<4i4d")

    def test_empty_knots(self):
        data = {
            "knots": [],
            "num_points": 0,
            "num_trefoils": 0,
            "keyframes": [],
            "equilibrium": False,
        }
        chunks = serialize_trefoil(data)
        assert "knot_0" not in chunks
        assert "meta" in chunks

    def test_no_core(self):
        data = {
            "knots": [],
            "num_points": 0,
            "num_trefoils": 0,
        }
        chunks = serialize_trefoil(data)
        assert "core" not in chunks


class TestSerializeMolecular:
    """Molecular structure serialization."""

    def test_atoms_and_bonds(self):
        data = {
            "atoms": [
                {"x": 0.0, "y": 0.0, "z": 0.0, "radius": 1.0},
                {"x": 1.0, "y": 0.0, "z": 0.0, "radius": 0.5},
            ],
            "bonds": [[0, 1, 1.0]],
            "atom_count": 2,
            "bond_count": 1,
        }
        chunks = serialize_molecular(data)
        assert "atoms" in chunks
        assert "bonds" in chunks
        assert "meta" in chunks
        # 2 atoms * 4 floats = 64 bytes
        assert len(chunks["atoms"]) == 64

    def test_empty(self):
        data = {"atoms": [], "bonds": []}
        chunks = serialize_molecular(data)
        assert "atoms" not in chunks
        assert "bonds" not in chunks
        assert "meta" in chunks


class TestSerializeQuantumCircuit:
    """Quantum circuit layout serialization."""

    def test_tracks_and_gates(self):
        data = {
            "qubit_tracks": [
                (0.0, 0.0, 0.0),
                (1.0, 1.0, 1.0),
            ],
            "gates": [
                {"position": [0.5, 0.5, 0.5], "size": 0.4},
            ],
            "qubits": 2,
            "depth": 1,
            "gate_count": 1,
        }
        chunks = serialize_quantum_circuit(data)
        assert "tracks" in chunks
        assert "gates" in chunks
        assert "meta" in chunks
        # 2 tracks * 3 floats = 48 bytes
        assert len(chunks["tracks"]) == 48
        # 1 gate * 4 floats = 32 bytes
        assert len(chunks["gates"]) == 32

    def test_empty(self):
        data = {"qubit_tracks": [], "gates": []}
        chunks = serialize_quantum_circuit(data)
        assert "tracks" not in chunks
        assert "gates" not in chunks
        assert "meta" in chunks
