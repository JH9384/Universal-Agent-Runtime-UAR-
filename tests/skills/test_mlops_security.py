"""Tests for mlops_security skills error paths."""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.mlops_security import (
    security_audit,
    pentest_scan,
    osint_recon,
    mlflow_track,
    mlflow_deploy,
    model_reg,
    kubeflow_pipe,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestSecurityAuditMissingDeps:
    """security_audit when bandit/safety not installed."""

    def test_bandit_missing(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = security_audit(
                _ctx({"audit_target": ".", "audit_tools": ["bandit"]})
            )
        assert result["status"] == "completed"
        assert "bandit" in result["results"]

    def test_safety_missing(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = security_audit(
                _ctx({"audit_tools": ["safety"]})
            )
        assert result["status"] == "completed"
        assert "safety" in result["results"]


class TestPentestScanMissingPackage:
    """pentest_scan when python-nmap not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value={"status": "failed", "error": "nmap missing"},
        ):
            result = pentest_scan(
                _ctx({"scan_target": "127.0.0.1"})
            )
        assert result["status"] == "failed"


class TestOSINTRecon:
    """osint_recon with DNS fallback (no external deps needed)."""

    def test_dns_lookup(self):
        with patch(
            "socket.gethostbyname",
            return_value="93.184.216.34",
        ):
            result = osint_recon(
                _ctx({"recon_target": "example.com", "recon_tools": ["dns"]})
            )
        assert result["status"] == "completed"
        assert result["target"] == "example.com"
        assert "dns" in result["results"]
        assert "ip" in result["results"]["dns"]

    def test_missing_target(self):
        result = osint_recon(_ctx({"recon_tools": ["dns"]}))
        assert result["status"] == "failed"


class TestMlflowTrackMissingPackage:
    """mlflow_track when mlflow not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value={"status": "failed", "error": "mlflow missing"},
        ):
            result = mlflow_track(_ctx({"mlflow_experiment": "test"}))
        assert result["status"] == "failed"


class TestMlflowDeployMissingPackage:
    """mlflow_deploy when mlflow not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value={"status": "failed", "error": "mlflow missing"},
        ):
            result = mlflow_deploy(_ctx({"mlflow_model_name": "model"}))
        assert result["status"] == "failed"

    def test_missing_model_name(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value=None,
        ):
            with patch.dict("sys.modules", {"mlflow": None}):
                result = mlflow_deploy(_ctx({}))
        # import error caught by skill_guard -> "error"
        assert result["status"] == "error"


class TestModelRegMissingPackage:
    """model_reg when mlflow not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value={"status": "failed", "error": "mlflow missing"},
        ):
            result = model_reg(
                _ctx({"mlflow_model_name": "m", "mlflow_run_id": "r"})
            )
        assert result["status"] == "failed"

    def test_missing_fields(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value=None,
        ):
            with patch.dict("sys.modules", {"mlflow": None}):
                result = model_reg(_ctx({}))
        assert result["status"] == "error"


class TestKubeflowPipeMissingPackage:
    """kubeflow_pipe when kfp not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.mlops_security.require_package",
            return_value={"status": "failed", "error": "kfp missing"},
        ):
            result = kubeflow_pipe(_ctx({"kfp_func_name": "pipe"}))
        assert result["status"] == "failed"
