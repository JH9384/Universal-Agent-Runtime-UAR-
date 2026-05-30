"""Tests for uar.skills.ml_tools."""

from unittest.mock import MagicMock, patch

from uar.skills.ml_tools import (
    optuna_tune,
    chromadb_store,
    flaml_auto,
    pycaret_ml,
)


class TestOptunaTune:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.ml_tools.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = optuna_tune(ctx)
        assert result["status"] == "error"


class TestChromaDBStore:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.ml_tools.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = chromadb_store(ctx)
        assert result["status"] == "error"


class TestOptunaTuneSuccess:
    def test_minimize_float(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "optuna_direction": "minimize",
            "optuna_n_trials": 5,
            "optuna_params": {
                "x": {"type": "float", "low": -10, "high": 10}
            },
            "optuna_objective": "x**2",
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            with patch.dict("sys.modules", {
                "optuna": MagicMock(),
                "numpy": MagicMock(),
            }):
                import sys
                mock_optuna = MagicMock()
                mock_study = MagicMock()
                mock_trial = MagicMock()
                mock_trial.value = 1.0
                mock_trial.params = {"x": 1.0}
                mock_study.best_trial = mock_trial
                mock_optuna.create_study.return_value = mock_study
                sys.modules["optuna"] = mock_optuna
                result = optuna_tune(ctx)
        assert result["status"] == "completed"
        assert result["best_value"] == 1.0

    def test_int_param(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "optuna_direction": "maximize",
            "optuna_n_trials": 3,
            "optuna_params": {
                "n": {"type": "int", "low": 1, "high": 10}
            },
            "optuna_objective": "n",
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            with patch.dict("sys.modules", {
                "optuna": MagicMock(),
                "numpy": MagicMock(),
            }):
                import sys
                mock_optuna = MagicMock()
                mock_study = MagicMock()
                mock_trial = MagicMock()
                mock_trial.value = 5
                mock_trial.params = {"n": 5}
                mock_study.best_trial = mock_trial
                mock_optuna.create_study.return_value = mock_study
                sys.modules["optuna"] = mock_optuna
                result = optuna_tune(ctx)
        assert result["status"] == "completed"

    def test_categorical_param(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "optuna_direction": "minimize",
            "optuna_n_trials": 3,
            "optuna_params": {
                "algo": {"type": "categorical", "choices": ["a", "b"]}
            },
            "optuna_objective": "0",
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            with patch.dict("sys.modules", {
                "optuna": MagicMock(),
                "numpy": MagicMock(),
            }):
                import sys
                mock_optuna = MagicMock()
                mock_study = MagicMock()
                mock_trial = MagicMock()
                mock_trial.value = 0.0
                mock_trial.params = {"algo": "a"}
                mock_study.best_trial = mock_trial
                mock_optuna.create_study.return_value = mock_study
                sys.modules["optuna"] = mock_optuna
                result = optuna_tune(ctx)
        assert result["status"] == "completed"


class TestChromaDBStoreSuccess:
    def test_add(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "chroma_operation": "add",
            "chroma_documents": ["doc1", "doc2"],
            "chroma_ids": ["id1", "id2"],
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            mock_collection = MagicMock()
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chromadb = MagicMock()
            mock_chromadb.Client.return_value = mock_client
            with patch.dict("sys.modules", {
                "chromadb": mock_chromadb,
                "chromadb.config": MagicMock(),
            }):
                result = chromadb_store(ctx)
        assert result["status"] == "completed"
        assert result["added"] == 2

    def test_query(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "chroma_operation": "query",
            "chroma_query": "test",
            "chroma_n_results": 3,
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "documents": [["d1"]],
                "distances": [[0.1]],
                "ids": [["id1"]],
            }
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chromadb = MagicMock()
            mock_chromadb.Client.return_value = mock_client
            with patch.dict("sys.modules", {
                "chromadb": mock_chromadb,
                "chromadb.config": MagicMock(),
            }):
                result = chromadb_store(ctx)
        assert result["status"] == "completed"
        assert result["query"] == "test"

    def test_peek(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"chroma_operation": "peek"}
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            mock_collection = MagicMock()
            mock_collection.peek.return_value = {"ids": ["id1"]}
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chromadb = MagicMock()
            mock_chromadb.Client.return_value = mock_client
            with patch.dict("sys.modules", {
                "chromadb": mock_chromadb,
                "chromadb.config": MagicMock(),
            }):
                result = chromadb_store(ctx)
        assert result["status"] == "completed"
        assert result["count"] == 1

    def test_delete(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "chroma_operation": "delete",
            "chroma_ids": ["id1", "id2"],
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            mock_collection = MagicMock()
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chromadb = MagicMock()
            mock_chromadb.Client.return_value = mock_client
            with patch.dict("sys.modules", {
                "chromadb": mock_chromadb,
                "chromadb.config": MagicMock(),
            }):
                result = chromadb_store(ctx)
        assert result["status"] == "completed"
        assert result["deleted"] == 2

    def test_unknown_operation(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"chroma_operation": "bad_op"}
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            mock_chromadb = MagicMock()
            with patch.dict("sys.modules", {
                "chromadb": mock_chromadb,
                "chromadb.config": MagicMock(),
            }):
                result = chromadb_store(ctx)
        assert result["status"] == "failed"

    def test_add_auto_ids(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "chroma_operation": "add",
            "chroma_documents": ["doc1"],
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            mock_collection = MagicMock()
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_chromadb = MagicMock()
            mock_chromadb.Client.return_value = mock_client
            with patch.dict("sys.modules", {
                "chromadb": mock_chromadb,
                "chromadb.config": MagicMock(),
            }):
                result = chromadb_store(ctx)
        assert result["status"] == "completed"


class TestFlamlAutoSuccess:
    def test_classification(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "flaml_task": "classification",
            "flaml_time_budget": 1,
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            with patch.dict("sys.modules", {
                "flaml": MagicMock(),
                "pandas": MagicMock(),
                "sklearn": MagicMock(),
                "sklearn.datasets": MagicMock(),
                "sklearn.model_selection": MagicMock(),
            }):
                import sys
                mock_flaml = MagicMock()
                mock_automl = MagicMock()
                mock_automl.best_estimator = "est"
                mock_automl.best_config = {"lr": 0.1}
                mock_automl.best_loss = 0.05
                mock_flaml.AutoML.return_value = mock_automl
                sys.modules["flaml"] = mock_flaml
                ds = sys.modules["sklearn.datasets"]
                ds.make_classification.return_value = ([[1]], [0])
                ms = sys.modules["sklearn.model_selection"]
                ms.train_test_split.return_value = (
                    [[1]], [[1]], [0], [0]
                )
                result = flaml_auto(ctx)
        assert result["status"] == "completed"
        assert result["task"] == "classification"

    def test_regression(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "flaml_task": "regression",
            "flaml_time_budget": 1,
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            with patch.dict("sys.modules", {
                "flaml": MagicMock(),
                "pandas": MagicMock(),
                "sklearn": MagicMock(),
                "sklearn.datasets": MagicMock(),
                "sklearn.model_selection": MagicMock(),
            }):
                import sys
                mock_flaml = MagicMock()
                mock_automl = MagicMock()
                mock_automl.best_estimator = "est"
                mock_automl.best_config = {"lr": 0.1}
                mock_automl.best_loss = 0.05
                mock_flaml.AutoML.return_value = mock_automl
                sys.modules["flaml"] = mock_flaml
                ds = sys.modules["sklearn.datasets"]
                ds.make_regression.return_value = ([[1]], [0])
                ms = sys.modules["sklearn.model_selection"]
                ms.train_test_split.return_value = (
                    [[1]], [[1]], [0], [0]
                )
                result = flaml_auto(ctx)
        assert result["status"] == "completed"
        assert result["task"] == "regression"


class TestPycaretMlSuccess:
    def test_classification_compare(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "pycaret_task": "classification",
            "pycaret_compare": True,
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            with patch.dict("sys.modules", {
                "pandas": MagicMock(),
                "pycaret.classification": MagicMock(),
                "sklearn": MagicMock(),
                "sklearn.datasets": MagicMock(),
            }):
                import sys
                mock_mod = MagicMock()
                mock_mod.compare_models.return_value = "best_model"
                sys.modules["pycaret.classification"] = mock_mod
                ds = sys.modules["sklearn.datasets"]
                mock_x = MagicMock()
                mock_x.shape = (500, 10)
                ds.make_classification.return_value = (mock_x, [0] * 500)
                result = pycaret_ml(ctx)
        assert result["status"] == "completed"
        assert result["compare"] is True

    def test_regression_create_model(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "pycaret_task": "regression",
            "pycaret_compare": False,
            "pycaret_model": "lr",
        }
        with patch("uar.skills.ml_tools.require_package", return_value=None):
            with patch.dict("sys.modules", {
                "pandas": MagicMock(),
                "pycaret.regression": MagicMock(),
                "sklearn": MagicMock(),
                "sklearn.datasets": MagicMock(),
            }):
                import sys
                mock_mod = MagicMock()
                mock_mod.create_model.return_value = "lr_model"
                sys.modules["pycaret.regression"] = mock_mod
                ds = sys.modules["sklearn.datasets"]
                mock_x = MagicMock()
                mock_x.shape = (500, 10)
                ds.make_regression.return_value = (mock_x, [0] * 500)
                result = pycaret_ml(ctx)
        assert result["status"] == "completed"
        assert result["compare"] is False


class TestFlamlAuto:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.ml_tools.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = flaml_auto(ctx)
        assert result["status"] == "error"
