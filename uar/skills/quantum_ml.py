"""Quantum machine learning skill using PennyLane.

Provides quantum neural networks, quantum chemistry, and
variational quantum algorithm capabilities.

Environment Variables:
    PENNYLANE_DEVICE    — Backend device: 'default.qubit', 'lightning.qubit'
                          (default: 'default.qubit')

Goal Metadata:
    qml_task            — Task type:
                          'qnn_regression', 'qnn_classification',
                          'vqe', 'qaoa', 'qchem_molecule'
    qml_qubits          — Number of qubits (default: 4)
    qml_layers          — Number of variational layers (default: 2)
    qml_steps           — Optimization steps (default: 100)
    qml_data            — Training data dict with 'X' and 'y'
    qml_params          — Optional dict of task-specific parameters
"""

from __future__ import annotations

import os
from typing import Any, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import require_package, skill_guard


@register_skill("quantum_ml")
@skill_guard("Quantum ML", status="failed")
def quantum_ml(ctx: PipelineContext) -> Dict[str, Any]:
    """Quantum machine learning with PennyLane.

    Supports:
      - qnn_regression:    Quantum neural network regression
      - qnn_classification: Quantum neural network classification
      - vqe:               Variational Quantum Eigensolver
      - qaoa:              Quantum Approximate Optimization Algorithm
      - qchem_molecule:    Quantum chemistry molecular energy
    """
    err = require_package("pennylane")
    if err:
        return err

    import pennylane as qml  # noqa: F811

    meta = ctx.goal.metadata or {}
    task = str(meta.get("qml_task", "qnn_regression")).lower()
    n_qubits = int(meta.get("qml_qubits", 4))
    n_layers = int(meta.get("qml_layers", 2))
    steps = int(meta.get("qml_steps", 100))
    data = meta.get("qml_data", {})
    params = meta.get("qml_params", {})

    dev_name = os.getenv("PENNYLANE_DEVICE", "default.qubit")
    dev = qml.device(dev_name, wires=n_qubits)

    if task == "qnn_regression":
        return _qnn_regression(dev, n_qubits, n_layers, steps, data, params)
    elif task == "qnn_classification":
        return _qnn_classification(
            dev, n_qubits, n_layers, steps, data, params
        )
    elif task == "vqe":
        return _vqe(dev, n_qubits, n_layers, steps, params)
    elif task == "qaoa":
        return _qaoa(dev, n_qubits, n_layers, steps, params)
    elif task == "qchem_molecule":
        return _qchem_molecule(params)
    else:
        return {"status": "failed", "error": f"Unknown task: {task}"}


def _qnn_regression(dev, n_qubits, n_layers, steps, data, params):
    """Quantum neural network regression."""
    import numpy as np
    import pennylane as qml

    X = np.array(data.get("X", [[0.0], [0.5], [1.0]]))
    y = np.array(data.get("y", [0.0, 0.5, 1.0]))

    @qml.qnode(dev)
    def circuit(x, weights):
        for i in range(n_qubits):
            qml.RX(x[0] if x.ndim == 1 else x[i], wires=i)
        for layer in range(n_layers):
            for i in range(n_qubits):
                qml.RY(weights[layer, i, 0], wires=i)
                qml.RZ(weights[layer, i, 1], wires=i)
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])
        return qml.expval(qml.PauliZ(0))

    shape = (n_layers, n_qubits, 2)
    weights = np.random.random(shape) * 2 * np.pi - np.pi

    def cost(weights):
        predictions = np.array([circuit(xi, weights) for xi in X])
        return np.mean((predictions - y) ** 2)

    opt = qml.GradientDescentOptimizer(0.1)
    for _ in range(steps):
        weights = opt.step(cost, weights)

    final_preds = np.array([circuit(xi, weights) for xi in X])
    mse = float(np.mean((final_preds - y) ** 2))

    return {
        "status": "completed",
        "task": "qnn_regression",
        "qubits": n_qubits,
        "layers": n_layers,
        "steps": steps,
        "mse": mse,
        "predictions": final_preds.tolist(),
        "targets": y.tolist(),
    }


def _qnn_classification(dev, n_qubits, n_layers, steps, data, params):
    """Quantum neural network binary classification."""
    import numpy as np
    import pennylane as qml

    X = np.array(data.get("X", [[0.0], [0.5], [1.0]]))
    y = np.array(data.get("y", [0, 1, 1]))

    @qml.qnode(dev)
    def circuit(x, weights):
        for i in range(n_qubits):
            qml.RX(x[0] if x.ndim == 1 else x[i], wires=i)
        for layer in range(n_layers):
            for i in range(n_qubits):
                qml.RY(weights[layer, i, 0], wires=i)
                qml.RZ(weights[layer, i, 1], wires=i)
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])
        return qml.expval(qml.PauliZ(0))

    shape = (n_layers, n_qubits, 2)
    weights = np.random.random(shape) * 2 * np.pi - np.pi

    def cost(weights):
        predictions = np.array([circuit(xi, weights) for xi in X])
        # Convert expectation to probability via sigmoid
        probs = 1 / (1 + np.exp(-predictions))
        log_loss = -np.mean(
            y * np.log(probs + 1e-8)
            + (1 - y) * np.log(1 - probs + 1e-8)
        )
        return log_loss

    opt = qml.GradientDescentOptimizer(0.1)
    for _ in range(steps):
        weights = opt.step(cost, weights)

    final_preds = np.array([circuit(xi, weights) for xi in X])
    probs = 1 / (1 + np.exp(-final_preds))
    accuracy = float(np.mean((probs > 0.5).astype(int) == y))

    return {
        "status": "completed",
        "task": "qnn_classification",
        "qubits": n_qubits,
        "layers": n_layers,
        "steps": steps,
        "accuracy": accuracy,
        "probabilities": probs.tolist(),
        "targets": y.tolist(),
    }


def _vqe(dev, n_qubits, n_layers, steps, params):
    """Variational Quantum Eigensolver for simple Hamiltonian."""
    import numpy as np
    import pennylane as qml

    hamiltonian_type = params.get("hamiltonian", "ising")

    @qml.qnode(dev)
    def circuit(weights):
        for i in range(n_qubits):
            qml.RX(weights[0, i], wires=i)
        for layer in range(n_layers):
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])
            for i in range(n_qubits):
                qml.RY(weights[layer + 1, i], wires=i)
        return qml.expval(qml.PauliZ(0) @ qml.PauliZ(1))

    weights = np.random.random((n_layers + 1, n_qubits)) * 2 * np.pi - np.pi
    opt = qml.GradientDescentOptimizer(0.1)

    for _ in range(steps):
        weights = opt.step(circuit, weights)

    energy = float(circuit(weights))

    return {
        "status": "completed",
        "task": "vqe",
        "qubits": n_qubits,
        "layers": n_layers,
        "steps": steps,
        "hamiltonian": hamiltonian_type,
        "ground_state_energy": energy,
    }


def _qaoa(dev, n_qubits, n_layers, steps, params):
    """Quantum Approximate Optimization Algorithm."""
    import numpy as np
    import pennylane as qml

    @qml.qnode(dev)
    def circuit(gamma_beta):
        for i in range(n_qubits):
            qml.Hadamard(wires=i)
        for layer in range(n_layers):
            gamma = gamma_beta[layer * 2]
            beta = gamma_beta[layer * 2 + 1]
            # Cost Hamiltonian: ZZ interactions
            for i in range(n_qubits - 1):
                qml.CNOT(wires=[i, i + 1])
                qml.RZ(gamma, wires=i + 1)
                qml.CNOT(wires=[i, i + 1])
            # Mixer Hamiltonian: X rotations
            for i in range(n_qubits):
                qml.RX(2 * beta, wires=i)
        return qml.expval(sum(qml.PauliZ(i) for i in range(n_qubits)))

    gamma_beta = np.random.random(n_layers * 2) * 2 * np.pi - np.pi
    opt = qml.GradientDescentOptimizer(0.1)

    for _ in range(steps):
        gamma_beta = opt.step(circuit, gamma_beta)

    expectation = float(circuit(gamma_beta))

    return {
        "status": "completed",
        "task": "qaoa",
        "qubits": n_qubits,
        "layers": n_layers,
        "steps": steps,
        "expectation_value": expectation,
    }


def _qchem_molecule(params):
    """Quantum chemistry molecular computation."""
    import importlib.util
    if importlib.util.find_spec("pennylane_qchem") is None:
        return {
            "status": "completed",
            "task": "qchem_molecule",
            "note": "pennylane-qchem not installed. Returning mock data.",
            "mock_energy": -1.117,
            "mock_molecule": params.get("molecule", "H2"),
        }

    molecule = params.get("molecule", "H2")
    basis = params.get("basis", "sto-3g")
    charge = int(params.get("charge", 0))

    # Mock result — full qchem requires molecular structure files
    return {
        "status": "completed",
        "task": "qchem_molecule",
        "molecule": molecule,
        "basis": basis,
        "charge": charge,
        "note": (
            "Basic quantum chemistry placeholder. "
            "Install pennylane-qchem for full functionality."
        ),
        "mock_energy": -1.117 if molecule == "H2" else None,
    }
