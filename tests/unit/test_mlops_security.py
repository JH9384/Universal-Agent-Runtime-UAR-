"""Tests for uar.skills.mlops_security."""

import os
from unittest.mock import MagicMock, patch

from uar.skills.mlops_security import (
    security_audit,
    pentest_scan,
    osint_recon,
    mlflow_track,
    mlflow_deploy,
    model_reg,
    kubeflow_pipe,
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


class TestSecurityAuditSuccess:
    def test_bandit_success_json(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"audit_tools": ["bandit"], "audit_format": "json"}
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout='{"results": [{"issue": "test"}]}',
                    stderr="",
                    returncode=0,
                )
                result = security_audit(ctx)
        assert result["status"] == "completed"
        assert "bandit" in result["results"]

    def test_bandit_success_text(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"audit_tools": ["bandit"], "audit_format": "text"}
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="issues found", stderr="", returncode=1
                )
                result = security_audit(ctx)
        assert result["status"] == "completed"

    def test_bandit_json_decode_error(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"audit_tools": ["bandit"], "audit_format": "json"}
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="not json", stderr="", returncode=0
                )
                result = security_audit(ctx)
        assert result["status"] == "completed"
        assert "raw" in str(result["results"]["bandit"])

    def test_safety_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"audit_tools": ["safety"]}
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="issues", stderr="", returncode=1
                )
                result = security_audit(ctx)
        assert result["status"] == "completed"
        assert "safety" in result["results"]

    def test_both_tools(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"audit_tools": ["bandit", "safety"]}
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(
                    stdout="ok", stderr="", returncode=0
                )
                result = security_audit(ctx)
        assert result["status"] == "completed"
        assert "bandit" in result["results"]
        assert "safety" in result["results"]


class TestPentestScanSuccess:
    def test_scan_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"scan_target": "127.0.0.1"}
        mock_scanner = MagicMock()
        mock_scanner.all_hosts.return_value = ["127.0.0.1"]
        mock_scanner.__getitem__ = lambda s, h: MagicMock(
            state=lambda: "up",
            all_protocols=lambda: ["tcp"],
            __getitem__=lambda s, p: {22: MagicMock(
                get=lambda k: "open" if k == "state" else "ssh"
            )},
        )
        mock_nmap = MagicMock()
        mock_nmap.PortScanner.return_value = mock_scanner
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {"nmap": mock_nmap}):
                result = pentest_scan(ctx)
        assert result["status"] == "completed"
        assert result["hosts_scanned"] >= 0


class TestOsintReconSuccess:
    def test_whois_with_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "recon_target": "example.com",
            "recon_tools": ["whois"],
        }
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            mock_whois_mod = MagicMock()
            mock_whois_mod.whois.return_value = MagicMock(
                registrar="ICANN",
                creation_date="2020-01-01",
                expiration_date="2030-01-01",
                name_servers=["ns1.example.com"],
            )
            with patch.dict("sys.modules", {"whois": mock_whois_mod}):
                result = osint_recon(ctx)
        assert result["status"] == "completed"
        assert "whois" in result["results"]

    def test_whois_fallback_exception(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "recon_target": "bad..domain",
            "recon_tools": ["whois"],
        }
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            mock_whois_mod = MagicMock()
            mock_whois_mod.whois.side_effect = Exception("bad domain")
            with patch.dict("sys.modules", {"whois": mock_whois_mod}):
                result = osint_recon(ctx)
        assert result["status"] == "completed"

    def test_dns(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "recon_target": "localhost",
            "recon_tools": ["dns"],
        }
        result = osint_recon(ctx)
        assert result["status"] == "completed"
        assert "dns" in result["results"]

    def test_dns_exception(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "recon_target": "not-a-valid-domain-12345.xyz",
            "recon_tools": ["dns"],
        }
        result = osint_recon(ctx)
        assert result["status"] == "completed"
        assert "dns" in result["results"]

    def test_shodan_with_key(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "recon_target": "8.8.8.8",
            "recon_tools": ["shodan"],
        }
        with patch.dict(os.environ, {"SHODAN_API_KEY": "fake_key"}):
            with patch(
                "uar.skills.mlops_security.require_package", return_value=None
            ):
                mock_api = MagicMock()
                mock_api.host.return_value = {
                    "ip_str": "8.8.8.8",
                    "org": "Google",
                    "os": None,
                    "ports": [53],
                }
                mock_shodan = MagicMock()
                mock_shodan.Shodan.return_value = mock_api
                with patch.dict("sys.modules", {"shodan": mock_shodan}):
                    result = osint_recon(ctx)
        assert result["status"] == "completed"
        assert "shodan" in result["results"]


class TestMLflowTrackSuccess:
    def test_log_params_and_metrics(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "mlflow_experiment": "test",
            "mlflow_params": {"lr": 0.01},
            "mlflow_metrics": {"acc": 0.95},
        }
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {"mlflow": MagicMock()}):
                import sys
                mock_mlflow = MagicMock()
                mock_run = MagicMock()
                mock_run.info.run_id = "run-123"
                mock_mlflow.start_run.return_value.__enter__ = lambda s: s
                mock_mlflow.start_run.return_value.__exit__ = (
                    lambda s, *a: None
                )
                mock_mlflow.active_run.return_value = mock_run
                sys.modules["mlflow"] = mock_mlflow
                result = mlflow_track(ctx)
        assert result["status"] == "completed"


class TestMLflowDeploySuccess:
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
            with patch.dict("sys.modules", {"mlflow": MagicMock()}):
                result = mlflow_deploy(ctx)
        assert result["status"] == "failed"

    def test_with_version(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "mlflow_model_name": "my-model",
            "mlflow_model_version": "3",
        }
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {"mlflow": MagicMock()}):
                import sys
                mock_mlflow = MagicMock()
                mock_model = MagicMock()
                mock_mlflow.pyfunc.load_model.return_value = mock_model
                sys.modules["mlflow"] = mock_mlflow
                result = mlflow_deploy(ctx)
        assert result["status"] == "completed"
        assert result["version"] == "3"

    def test_latest_with_stage(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "mlflow_model_name": "my-model",
            "mlflow_model_version": "latest",
            "mlflow_stage": "Production",
        }
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {"mlflow": MagicMock()}):
                import sys
                mock_mlflow = MagicMock()
                mock_client = MagicMock()
                mock_mv = MagicMock()
                mock_mv.version = "2"
                mock_client.get_latest_versions.return_value = [mock_mv]
                mock_mlflow.tracking.MlflowClient.return_value = mock_client
                mock_model = MagicMock()
                mock_mlflow.pyfunc.load_model.return_value = mock_model
                sys.modules["mlflow"] = mock_mlflow
                result = mlflow_deploy(ctx)
        assert result["status"] == "completed"


class TestModelReg:
    def test_missing_fields(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {"mlflow": MagicMock()}):
                result = model_reg(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "mlflow_model_name": "my-model",
            "mlflow_run_id": "run-123",
        }
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {"mlflow": MagicMock()}):
                import sys
                mock_mlflow = MagicMock()
                mock_result = MagicMock()
                mock_result.version = "1"
                mock_mlflow.register_model.return_value = mock_result
                sys.modules["mlflow"] = mock_mlflow
                result = model_reg(ctx)
        assert result["status"] == "completed"
        assert result["version"] == "1"

    def test_success_with_stage(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "mlflow_model_name": "my-model",
            "mlflow_run_id": "run-123",
            "mlflow_stage": "Production",
        }
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {"mlflow": MagicMock()}):
                import sys
                mock_mlflow = MagicMock()
                mock_result = MagicMock()
                mock_result.version = "2"
                mock_mlflow.register_model.return_value = mock_result
                sys.modules["mlflow"] = mock_mlflow
                result = model_reg(ctx)
        assert result["status"] == "completed"


class TestKubeflowPipe:
    def test_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {
            "kfp_func_name": "test_pipe",
            "kfp_steps": [
                {"name": "step1", "image": "python:3.9"}
            ],
        }
        with patch(
            "uar.skills.mlops_security.require_package", return_value=None
        ):
            with patch.dict("sys.modules", {
                "kfp": MagicMock(),
                "kfp.dsl": MagicMock(),
                "kfp.compiler": MagicMock(),
            }):
                import sys
                mock_kfp = MagicMock()
                mock_dsl = MagicMock()
                mock_compiler = MagicMock()
                sys.modules["kfp"] = mock_kfp
                sys.modules["kfp.dsl"] = mock_dsl
                sys.modules["kfp.compiler"] = mock_compiler
                result = kubeflow_pipe(ctx)
        assert result["status"] == "completed"
        assert result["pipeline_name"] == "test_pipe"
