"""Tests for mlops_security skills with mocked heavy deps."""

from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestSecurityAuditMocked:
    """security_audit with mocked subprocess."""

    def test_bandit_json(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = (
            '{"results": [{"test_id": "B101", "issue_text": "x"}]}'
        )
        mock_proc.stderr = ""

        with patch(
            "uar.skills.mlops_security.subprocess.run",
            return_value=mock_proc,
        ):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import security_audit
                result = security_audit(
                    _ctx({
                        "audit_target": ".",
                        "audit_tools": ["bandit"],
                        "audit_format": "json",
                    })
                )
        assert result["status"] == "completed"
        bandit = result["results"]["bandit"]
        assert bandit["status"] == "completed"
        assert bandit["issues_count"] == 1

    def test_safety_run(self):
        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "No issues"
        mock_proc.stderr = ""

        with patch(
            "uar.skills.mlops_security.subprocess.run",
            return_value=mock_proc,
        ):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import security_audit
                result = security_audit(
                    _ctx({"audit_tools": ["safety"]})
                )
        assert result["status"] == "completed"
        safety = result["results"]["safety"]
        assert safety["status"] == "completed"
        assert safety["issues"] is False


class TestPentestScanMocked:
    """pentest_scan with mocked python-nmap."""

    def test_scan_localhost(self):
        mock_scanner = MagicMock()
        mock_scanner.all_hosts.return_value = ["127.0.0.1"]
        mock_scanner.__getitem__ = lambda self, h: {
            "127.0.0.1": MagicMock(
                state=MagicMock(return_value="up"),
                all_protocols=MagicMock(return_value=["tcp"]),
                __getitem__=lambda self, p: {
                    "tcp": {
                        80: {
                            "state": "open",
                            "name": "http",
                            "product": "nginx",
                            "version": "1.18",
                        }
                    }
                },
            ),
        }.get(h, MagicMock())
        mock_nmap = MagicMock()
        mock_nmap.PortScanner.return_value = mock_scanner

        with patch.dict("sys.modules", {"nmap": mock_nmap}):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import pentest_scan
                result = pentest_scan(
                    _ctx({
                        "scan_target": "127.0.0.1",
                        "scan_ports": "80",
                    })
                )
        assert result["status"] == "completed"
        assert result["hosts_scanned"] == 1
        assert result["hosts"][0]["host"] == "127.0.0.1"


class TestOSINTReconMocked:
    """osint_recon with mocked whois and shodan."""

    def test_whois_real(self):
        mock_whois = MagicMock()
        mock_result = MagicMock()
        mock_result.registrar = "Example Registrar"
        mock_result.creation_date = "2020-01-01"
        mock_result.expiration_date = "2025-01-01"
        mock_result.name_servers = ["ns1.example.com"]
        mock_whois.whois.return_value = mock_result

        with patch.dict("sys.modules", {"whois": mock_whois}):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import osint_recon
                result = osint_recon(
                    _ctx({
                        "recon_target": "example.com",
                        "recon_tools": ["whois"],
                    })
                )
        assert result["status"] == "completed"
        whois_result = result["results"]["whois"]
        assert whois_result["status"] == "completed"
        assert whois_result["registrar"] == "Example Registrar"

    def test_shodan_with_key(self):
        mock_shodan = MagicMock()
        mock_api = MagicMock()
        mock_api.host.return_value = {
            "ip_str": "1.2.3.4",
            "org": "Example Org",
            "os": None,
            "ports": [80, 443],
        }
        mock_shodan.Shodan.return_value = mock_api

        with patch.dict(
            "sys.modules", {"shodan": mock_shodan}
        ), patch.dict(
            "os.environ", {"SHODAN_API_KEY": "fake_key"}
        ):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import osint_recon
                result = osint_recon(
                    _ctx({
                        "recon_target": "1.2.3.4",
                        "recon_tools": ["shodan"],
                    })
                )
        assert result["status"] == "completed"
        shodan_result = result["results"]["shodan"]
        assert shodan_result["status"] == "completed"
        assert shodan_result["ip"] == "1.2.3.4"

    def test_shodan_no_key(self):
        with patch.dict("os.environ", {}, clear=True):
            from uar.skills.mlops_security import osint_recon
            result = osint_recon(
                _ctx({
                    "recon_target": "1.2.3.4",
                    "recon_tools": ["shodan"],
                })
            )
        assert result["status"] == "completed"
        assert "shodan" in result["results"]
        assert "SHODAN_API_KEY" in result["results"]["shodan"]["info"]


class TestMlflowTrackMocked:
    """mlflow_track with mocked mlflow."""

    def test_log_params_and_metrics(self):
        mock_mlflow = MagicMock()
        mock_run = MagicMock()
        mock_run.info.run_id = "run-123"
        mock_mlflow.active_run.return_value = mock_run

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import mlflow_track
                result = mlflow_track(
                    _ctx({
                        "mlflow_experiment": "exp1",
                        "mlflow_run_name": "run1",
                        "mlflow_params": {"lr": 0.01},
                        "mlflow_metrics": {"acc": 0.95},
                    })
                )
        assert result["status"] == "completed"
        assert result["run_id"] == "run-123"
        assert result["experiment"] == "exp1"
        mock_mlflow.log_params.assert_called_once_with({"lr": 0.01})
        mock_mlflow.log_metrics.assert_called_once_with({"acc": 0.95})


class TestMlflowDeployMocked:
    """mlflow_deploy with mocked mlflow."""

    def test_load_specific_version(self):
        mock_mlflow = MagicMock()
        mock_model = MagicMock()
        mock_mlflow.pyfunc.load_model.return_value = mock_model

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import mlflow_deploy
                result = mlflow_deploy(
                    _ctx({
                        "mlflow_model_name": "my_model",
                        "mlflow_model_version": "3",
                    })
                )
        assert result["status"] == "completed"
        assert result["model_name"] == "my_model"
        assert result["version"] == "3"
        mock_mlflow.pyfunc.load_model.assert_called_once()


class TestModelRegMocked:
    """model_reg with mocked mlflow."""

    def test_register_and_stage(self):
        mock_mlflow = MagicMock()
        mock_result = MagicMock()
        mock_result.version = "2"
        mock_mlflow.register_model.return_value = mock_result
        mock_client = MagicMock()
        mock_mlflow.tracking.MlflowClient.return_value = mock_client

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import model_reg
                result = model_reg(
                    _ctx({
                        "mlflow_model_name": "m",
                        "mlflow_run_id": "r",
                        "mlflow_stage": "Staging",
                    })
                )
        assert result["status"] == "completed"
        assert result["version"] == "2"
        assert result["stage"] == "Staging"
        mock_client.transition_model_version_stage.assert_called_once()

    def test_register_no_stage(self):
        mock_mlflow = MagicMock()
        mock_result = MagicMock()
        mock_result.version = "1"
        mock_mlflow.register_model.return_value = mock_result

        with patch.dict("sys.modules", {"mlflow": mock_mlflow}):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import model_reg
                result = model_reg(
                    _ctx({
                        "mlflow_model_name": "m",
                        "mlflow_run_id": "r",
                    })
                )
        assert result["status"] == "completed"
        assert result["version"] == "1"
        assert result["stage"] is None


class TestKubeflowPipeMocked:
    """kubeflow_pipe with mocked kfp."""

    def test_compile_pipeline(self):
        import types
        mock_dsl = MagicMock()
        mock_dsl.pipeline = lambda name: lambda f: f
        mock_dsl.ContainerOp = MagicMock()
        mock_compiler = MagicMock()

        # Build a fake module tree so `from kfp import dsl` and
        # `from kfp.compiler import Compiler` work inside the skill.
        mock_kfp = types.ModuleType("kfp")
        mock_kfp.dsl = mock_dsl
        mock_compiler_mod = types.ModuleType("kfp.compiler")
        # Compiler() call should return the mock_compiler instance
        mock_compiler_mod.Compiler = MagicMock(return_value=mock_compiler)
        mock_kfp.compiler = mock_compiler_mod

        with patch.dict("sys.modules", {
            "kfp": mock_kfp,
            "kfp.compiler": mock_compiler_mod,
        }):
            with patch(
                "uar.skills.mlops_security.require_package",
                return_value=None,
            ):
                from uar.skills.mlops_security import kubeflow_pipe
                result = kubeflow_pipe(
                    _ctx({
                        "kfp_func_name": "test_pipe",
                        "kfp_output_path": "test.yaml",
                        "kfp_steps": [
                            {"name": "step1", "image": "python:3.9"},
                        ],
                    })
                )
        assert result["status"] == "completed"
        assert result["pipeline_name"] == "test_pipe"
        assert result["output_path"] == "test.yaml"
        mock_compiler.compile.assert_called_once()
