"""Tests for quantum_ml skill.

Full PennyLane paths are tested by patching the internal helpers;
missing-dependency paths are tested directly.
"""

from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.quantum_ml import quantum_ml


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(id="t", user_intent="t", objective="t", metadata=meta)
    )


class TestQuantumMLMocked:
    """quantum_ml with patched internal helpers."""

    def test_qnn_regression(self):
        with patch.dict("sys.modules", {"pennylane": MagicMock()}):
            with patch(
                "uar.skills.quantum_ml._qnn_regression",
                return_value={"status": "completed", "task": "qnn_regression"},
            ):
                with patch(
                    "uar.skills.quantum_ml.require_package",
                    return_value=None,
                ):
                    result = quantum_ml(
                        _ctx({"qml_task": "qnn_regression"})
                    )
        assert result["status"] == "completed"
        assert result["task"] == "qnn_regression"

    def test_qnn_classification(self):
        with patch.dict("sys.modules", {"pennylane": MagicMock()}):
            with patch(
                "uar.skills.quantum_ml._qnn_classification",
                return_value={
                    "status": "completed", "task": "qnn_classification"
                },
            ):
                with patch(
                    "uar.skills.quantum_ml.require_package",
                    return_value=None,
                ):
                    result = quantum_ml(
                        _ctx({"qml_task": "qnn_classification"})
                    )
        assert result["status"] == "completed"
        assert result["task"] == "qnn_classification"

    def test_vqe(self):
        with patch.dict("sys.modules", {"pennylane": MagicMock()}):
            with patch(
                "uar.skills.quantum_ml._vqe",
                return_value={"status": "completed", "task": "vqe"},
            ):
                with patch(
                    "uar.skills.quantum_ml.require_package",
                    return_value=None,
                ):
                    result = quantum_ml(
                        _ctx({"qml_task": "vqe"})
                    )
        assert result["status"] == "completed"
        assert result["task"] == "vqe"

    def test_qaoa(self):
        with patch.dict("sys.modules", {"pennylane": MagicMock()}):
            with patch(
                "uar.skills.quantum_ml._qaoa",
                return_value={"status": "completed", "task": "qaoa"},
            ):
                with patch(
                    "uar.skills.quantum_ml.require_package",
                    return_value=None,
                ):
                    result = quantum_ml(
                        _ctx({"qml_task": "qaoa"})
                    )
        assert result["status"] == "completed"
        assert result["task"] == "qaoa"

    def test_qchem_molecule(self):
        with patch.dict("sys.modules", {"pennylane": MagicMock()}):
            with patch(
                "uar.skills.quantum_ml._qchem_molecule",
                return_value={
                    "status": "completed", "task": "qchem_molecule"
                },
            ):
                with patch(
                    "uar.skills.quantum_ml.require_package",
                    return_value=None,
                ):
                    result = quantum_ml(
                        _ctx({"qml_task": "qchem_molecule"})
                    )
        assert result["status"] == "completed"
        assert result["task"] == "qchem_molecule"

    def test_unknown_task(self):
        with patch.dict("sys.modules", {"pennylane": MagicMock()}):
            with patch(
                "uar.skills.quantum_ml.require_package",
                return_value=None,
            ):
                result = quantum_ml(
                    _ctx({"qml_task": "unknown"})
                )
        assert result["status"] == "failed"

    def test_missing_dependency(self):
        with patch(
            "uar.skills.quantum_ml.require_package",
            return_value={"status": "failed", "error": "pennylane missing"},
        ):
            result = quantum_ml(_ctx({"qml_task": "vqe"}))
        assert result["status"] == "failed"
