"""Tests for uar.skills.mlops_security."""

from unittest.mock import MagicMock, patch

from uar.skills.mlops_security import (
    security_audit,
    pentest_scan,
    osint_recon,
    mlflow_track,
    mlflow_deploy,
)


class TestSecurityAudit:
    def test_bandit_missing(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"audit_tools": ["bandit"]}
        with patch("uar.skills.mlops_security.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = security_audit(ctx)
        assert result["status"] == "error"
        assert "bandit" in result["results"]

    def test_safety_missing(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"audit_tools": ["safety"]}
        with patch("uar.skills.mlops_security.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = security_audit(ctx)
        assert result["status"] == "error"
        assert "safety" in result["results"]


class TestPentestScan:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.mlops_security.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = pentest_scan(ctx)
        assert result["status"] == "error"


class TestOsintRecon:
    def test_no_target(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        result = osint_recon(ctx)
        assert result["status"] == "failed"

    def test_dns_only(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "recon_target": "localhost",
            "recon_tools": ["dns"],
        }
        result = osint_recon(ctx)
        assert result["status"] == "completed"
        assert "dns" in result["results"]

    def test_shodan_no_key(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "recon_target": "localhost",
            "recon_tools": ["shodan"],
        }
        result = osint_recon(ctx)
        assert result["status"] == "completed"
        assert "shodan" in result["results"]
        assert "SHODAN_API_KEY" in str(result["results"]["shodan"])


class TestMLflowTrack:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.mlops_security.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = mlflow_track(ctx)
        assert result["status"] == "error"


class TestMLflowDeploy:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.mlops_security.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = mlflow_deploy(ctx)
        assert result["status"] == "error"

    def test_missing_model_name(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            result = mlflow_deploy(ctx)
        assert result["status"] == "failed"
