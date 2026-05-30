"""Tests for uar.skills.ml_tools."""

from unittest.mock import MagicMock, patch

from uar.skills.ml_tools import optuna_tune, chromadb_store, flaml_auto


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


class TestFlamlAuto:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.ml_tools.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = flaml_auto(ctx)
        assert result["status"] == "error"
