"""Tests for ml_tools with mocked Optuna and ChromaDB.

Covers all operations when deps are mocked as available.
"""

from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.ml_tools import optuna_tune, chromadb_store


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(id="t", user_intent="t", objective="t", metadata=meta)
    )


class TestOptunaTuneMocked:
    """optuna_tune with mocked optuna."""

    def _mock_optuna(self):
        mock_study = MagicMock()
        mock_study.best_trial.value = 0.5
        mock_study.best_trial.params = {"x": 1.0}
        mock_optuna = MagicMock()
        mock_optuna.create_study.return_value = mock_study
        return mock_optuna

    def test_minimize(self):
        optuna = self._mock_optuna()
        with patch.dict("sys.modules", {
            "optuna": optuna, "numpy": MagicMock()
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = optuna_tune(
                    _ctx({
                        "optuna_objective": "x**2",
                        "optuna_direction": "minimize",
                        "optuna_n_trials": 5,
                        "optuna_params": {
                            "x": {"type": "float", "low": -10, "high": 10}
                        },
                    })
                )
        assert result["status"] == "completed"
        assert result["direction"] == "minimize"
        assert result["best_value"] == 0.5

    def test_int_param(self):
        optuna = self._mock_optuna()
        with patch.dict("sys.modules", {
            "optuna": optuna, "numpy": MagicMock()
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = optuna_tune(
                    _ctx({
                        "optuna_objective": "x",
                        "optuna_params": {
                            "x": {"type": "int", "low": 0, "high": 10}
                        },
                    })
                )
        assert result["status"] == "completed"

    def test_categorical_param(self):
        optuna = self._mock_optuna()
        with patch.dict("sys.modules", {
            "optuna": optuna, "numpy": MagicMock()
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = optuna_tune(
                    _ctx({
                        "optuna_objective": "x",
                        "optuna_params": {
                            "x": {
                                "type": "categorical",
                                "choices": ["a", "b"],
                            }
                        },
                    })
                )
        assert result["status"] == "completed"


class TestChromaDBStoreMocked:
    """chromadb_store with mocked chromadb."""

    def _setup(self):
        mock_collection = MagicMock()
        mock_collection.query.return_value = {
            "documents": [["doc1"]],
            "distances": [[0.1]],
            "ids": [["id1"]],
        }
        mock_collection.peek.return_value = {
            "ids": ["id1"],
        }
        mock_client = MagicMock()
        mock_client.get_or_create_collection.return_value = mock_collection
        mock_chromadb = MagicMock()
        mock_chromadb.Client.return_value = mock_client
        mock_settings = MagicMock()
        return mock_chromadb, mock_settings, mock_collection

    def test_query(self):
        mock_chromadb, mock_settings, _ = self._setup()
        with patch.dict("sys.modules", {
            "chromadb": mock_chromadb,
            "chromadb.config": MagicMock(Settings=mock_settings),
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = chromadb_store(
                    _ctx({
                        "chroma_operation": "query",
                        "chroma_query": "test",
                        "chroma_n_results": 3,
                    })
                )
        assert result["status"] == "completed"
        assert result["query"] == "test"

    def test_add(self):
        mock_chromadb, mock_settings, _ = self._setup()
        with patch.dict("sys.modules", {
            "chromadb": mock_chromadb,
            "chromadb.config": MagicMock(Settings=mock_settings),
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = chromadb_store(
                    _ctx({
                        "chroma_operation": "add",
                        "chroma_documents": ["hello"],
                        "chroma_ids": ["doc_0"],
                    })
                )
        assert result["status"] == "completed"
        assert result["added"] == 1

    def test_add_without_ids(self):
        mock_chromadb, mock_settings, _ = self._setup()
        with patch.dict("sys.modules", {
            "chromadb": mock_chromadb,
            "chromadb.config": MagicMock(Settings=mock_settings),
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = chromadb_store(
                    _ctx({
                        "chroma_operation": "add",
                        "chroma_documents": ["hello"],
                    })
                )
        assert result["status"] == "completed"

    def test_peek(self):
        mock_chromadb, mock_settings, _ = self._setup()
        with patch.dict("sys.modules", {
            "chromadb": mock_chromadb,
            "chromadb.config": MagicMock(Settings=mock_settings),
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = chromadb_store(
                    _ctx({"chroma_operation": "peek"})
                )
        assert result["status"] == "completed"

    def test_delete(self):
        mock_chromadb, mock_settings, _ = self._setup()
        with patch.dict("sys.modules", {
            "chromadb": mock_chromadb,
            "chromadb.config": MagicMock(Settings=mock_settings),
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = chromadb_store(
                    _ctx({
                        "chroma_operation": "delete",
                        "chroma_ids": ["id1"],
                    })
                )
        assert result["status"] == "completed"
        assert result["deleted"] == 1

    def test_unknown_operation(self):
        mock_chromadb, mock_settings, _ = self._setup()
        with patch.dict("sys.modules", {
            "chromadb": mock_chromadb,
            "chromadb.config": MagicMock(Settings=mock_settings),
        }):
            with patch(
                "uar.skills.ml_tools.require_package",
                return_value=None,
            ):
                result = chromadb_store(
                    _ctx({"chroma_operation": "merge"})
                )
        assert result["status"] == "failed"
        assert "Unknown operation" in result["error"]
