"""Quantum circuit 3D visualization skill.

Generates spatial layouts for quantum circuits including qubit
registers, gates as 3D objects, and entanglement connections.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext


_GATE_SHAPES: Dict[str, str] = {
    "H": "cube",
    "X": "octahedron",
    "Y": "diamond",
    "Z": "tetrahedron",
    "CNOT": "sphere",
    "RX": "cylinder",
    "RY": "cylinder",
    "RZ": "cylinder",
    "T": "pyramid",
    "S": "pyramid",
    "SWAP": "double_cone",
    "MEASURE": "ring",
}

_GATE_COLORS: Dict[str, str] = {
    "H": "#3b82f6",
    "X": "#ef4444",
    "Y": "#22c55e",
    "Z": "#f59e0b",
    "CNOT": "#a855f7",
    "RX": "#06b6d4",
    "RY": "#ec4899",
    "RZ": "#14b8a6",
    "T": "#6366f1",
    "S": "#8b5cf6",
    "SWAP": "#f97316",
    "MEASURE": "#64748b",
}


def _build_circuit(
    qubits: int,
    depth: int,
    gate_sequence: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    """Build a quantum circuit layout in 3D space.

    Qubits arranged along Y axis, gates placed at X positions,
    entanglement connections drawn in Z.
    """
    # Default gate sequence if none provided
    if gate_sequence is None:
        gate_sequence = _default_circuit(qubits, depth)

    qubit_tracks: List[List[float]] = []
    for q in range(qubits):
        y = (q - (qubits - 1) / 2.0) * 2.0
        qubit_tracks.append([0.0, y, 0.0])

    gates: List[Dict[str, Any]] = []
    connections: List[Tuple[int, int, int, int]] = []

    for g in gate_sequence:
        gate_type = g.get("gate", "H")
        targets = g.get("targets", [0])
        controls = g.get("controls", [])
        step = g.get("step", 0)

        x = (step - depth / 2.0) * 2.0

        # Main gate on target qubit
        for t in targets:
            y = (t - (qubits - 1) / 2.0) * 2.0
            gates.append({
                "type": gate_type,
                "shape": _GATE_SHAPES.get(gate_type, "cube"),
                "color": _GATE_COLORS.get(gate_type, "#888888"),
                "position": [x, y, 0.0],
                "qubit": t,
                "step": step,
                "size": 0.4,
            })

        # Control qubits (for multi-qubit gates)
        for c in controls:
            y = (c - (qubits - 1) / 2.0) * 2.0
            gates.append({
                "type": "control",
                "shape": "sphere",
                "color": "#ffffff",
                "position": [x, y, 0.0],
                "qubit": c,
                "step": step,
                "size": 0.15,
            })
            # Entanglement connection
            for t in targets:
                connections.append((c, t, step, step))

    return {
        "qubits": qubits,
        "depth": depth,
        "qubit_tracks": qubit_tracks,
        "gates": gates,
        "connections": connections,
        "gate_count": len(gates),
    }


def _default_circuit(
    qubits: int, depth: int
) -> List[Dict[str, Any]]:
    """Generate a default Bell-state / GHZ circuit."""
    seq: List[Dict[str, Any]] = []
    step = 0

    # Hadamard on first qubit
    seq.append({"gate": "H", "targets": [0], "step": step})
    step += 1

    # CNOT chain
    for i in range(min(qubits - 1, depth - 2)):
        seq.append({
            "gate": "CNOT",
            "targets": [i + 1],
            "controls": [i],
            "step": step,
        })
        step += 1

    # Add some rotation gates
    for i in range(min(qubits, depth - step)):
        seq.append({
            "gate": "RZ",
            "targets": [i % qubits],
            "step": step,
        })
        step += 1

    # Measurements
    for i in range(min(qubits, depth - step)):
        seq.append({
            "gate": "MEASURE",
            "targets": [i % qubits],
            "step": step,
        })
        step += 1

    return seq


def quantum_circuit_visualization(
    ctx: PipelineContext,
) -> Dict[str, Any]:
    """Generate 3D quantum circuit layout data.

    Parameters (from ctx.goal.metadata):
        qubits: int - number of qubits (default: 4)
        depth: int - circuit depth steps (default: 8)
        gate_sequence: list - optional custom gate list
    """
    params = ctx.goal.metadata or {}
    qubits = int(params.get("qubits", 4))
    depth = int(params.get("depth", 8))
    gate_sequence = params.get("gate_sequence")

    circuit = _build_circuit(qubits, depth, gate_sequence)

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": circuit,
        "metrics": {
            "qubits": qubits,
            "depth": depth,
            "gates": circuit["gate_count"],
            "entanglements": len(circuit["connections"]),
        },
    }


register_skill("quantum_circuit_visualization")(
    quantum_circuit_visualization
)
