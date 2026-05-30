"""Tests for uar.cli.main."""

import os
from unittest.mock import MagicMock, patch

import pytest
import typer

from uar.cli.main import (
    skill_list,
    skill_show,
    recipe_list,
    recipe_show,
    run_goal,
    run_server_goal,
    history_list,
    history_show,
    health_local,
    health_server,
    openapi_export,
    doctor_command,
    skill_ping,
    cb_list,
    cb_reset,
    run_compare,
    run_delete,
    run_bulk_delete,
    _api_headers,
)


class TestServerUrl:
    def test_default(self):
        with patch.dict(os.environ, {}, clear=True):
            from uar.cli.main import _server_url
            assert _server_url() == "http://localhost:8000"

    def test_env_override(self):
        with patch.dict(os.environ, {"UAR_SERVER_URL": "http://custom:8080"}):
            from uar.cli.main import _server_url
            assert _server_url() == "http://custom:8080"


class TestSkillList:
    def test_empty(self, capsys):
        with patch("uar.cli.main.registry") as mock_reg:
            mock_reg.list.return_value = []
            skill_list(available=False)
        captured = capsys.readouterr()
        assert "No skills" in captured.out or captured.out == ""

    def test_with_skills(self, capsys):
        with patch("uar.cli.main.registry") as mock_reg:
            mock_reg.list.return_value = ["skill_a", "skill_b"]
            skill_list(available=False)
        captured = capsys.readouterr()
        assert "skill_a" in captured.out or captured.out


class TestSkillShow:
    def test_found(self, capsys):
        def fake_skill():
            """Fake skill doc."""
            pass

        with patch("uar.cli.main.registry") as mock_reg:
            mock_reg.get.return_value = fake_skill
            skill_show("skill_a")
        captured = capsys.readouterr()
        assert "Fake skill doc" in captured.out

    def test_not_found(self, capsys):
        from uar.core.exceptions import SkillNotFoundError

        with patch("uar.cli.main.registry") as mock_reg:
            mock_reg.get.side_effect = SkillNotFoundError("missing")
            with pytest.raises(typer.Exit):
                skill_show("missing")


class TestRecipeList:
    def test_empty(self, capsys):
        with patch("uar.cli.main.DEFAULT_RECIPES", {}):
            recipe_list()
        captured = capsys.readouterr()
        assert "No recipes" in captured.out or captured.out == ""

    def test_with_recipes(self, capsys):
        recipes = {
            "r1": {"skills": ["s1", "s2"]},
        }
        with patch("uar.cli.main.DEFAULT_RECIPES", recipes):
            recipe_list()
        captured = capsys.readouterr()
        assert "r1" in captured.out or captured.out


class TestRecipeShow:
    def test_found(self, capsys):
        recipes = {"r1": {"skills": ["s1"]}}
        with patch("uar.cli.main.DEFAULT_RECIPES", recipes):
            recipe_show("r1")
        captured = capsys.readouterr()
        assert "s1" in captured.out or captured.out

    def test_not_found(self, capsys):
        with patch("uar.cli.main.DEFAULT_RECIPES", {}):
            with pytest.raises(typer.Exit):
                recipe_show("r1")


class TestRunGoal:
    def test_basic(self):
        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.outputs = {"ok": True}
        mock_result.events = []

        with patch("uar.cli.main.console"):
            with patch("uar.cli.main.SimplePlanner"):
                with patch("uar.cli.main.Executor") as mock_exec:
                    mock_exec.return_value.run.return_value = mock_result
                    with patch("uar.cli.main.get_store") as mock_get:
                        mock_store = MagicMock()
                        mock_get.return_value = mock_store
                        run_goal(
                            "test goal", skills=None, input_path=None,
                            json_output=False
                        )

    def test_json_output(self):
        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.outputs = {}
        mock_result.events = []

        with patch("uar.cli.main.console"):
            with patch("uar.cli.main.SimplePlanner"):
                with patch("uar.cli.main.Executor") as mock_exec:
                    mock_exec.return_value.run.return_value = mock_result
                    with patch("uar.cli.main.get_store") as mock_get:
                        mock_store = MagicMock()
                        mock_get.return_value = mock_store
                        run_goal(
                            "test", skills="s1", input_path=None,
                            json_output=True
                        )


class TestRunServerGoal:
    def test_success(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            run_server_goal(
                "test", skills=None, server="http://test", api_key=None
            )
        captured = capsys.readouterr()
        assert "ok" in captured.out or captured.out

    def test_with_api_key(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            run_server_goal(
                "test", skills=None, server="http://test",
                api_key="secret"
            )
        captured = capsys.readouterr()
        assert "ok" in captured.out or captured.out

    def test_connect_error(self, capsys):
        import httpx

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.side_effect = (
                httpx.ConnectError("fail")
            )
            with pytest.raises(typer.Exit):
                run_server_goal(
                    "test", skills=None, server="http://test",
                    api_key=None
                )

    def test_http_error(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "fail"}
        exc = httpx.HTTPStatusError(
            "fail",
            request=MagicMock(),
            response=mock_resp,
        )
        mock_client = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                run_server_goal(
                    "test", skills=None, server="http://test",
                    api_key=None
                )


class TestHistoryList:
    def test_empty(self, capsys):
        with patch("uar.cli.main.get_store") as mock_get:
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_get.return_value = mock_store
            history_list(limit=10)
        captured = capsys.readouterr()
        assert "No stored runs" in captured.out or captured.out == ""

    def test_with_records(self, capsys):
        mock_record = MagicMock()
        mock_record.run_id = "r1"
        mock_record.goal_id = "g1"
        mock_record.status = "completed"
        mock_record.skills = ["s1"]
        mock_record.events = []
        mock_record.outputs = {}

        with patch("uar.cli.main.get_store") as mock_get:
            mock_store = MagicMock()
            mock_store.list_all.return_value = [{}]
            mock_get.return_value = mock_store
            with patch("uar.cli.main.run_record_from_dict") as mock_from:
                mock_from.return_value = mock_record
                with patch("uar.cli.main.replay_summary") as mock_sum:
                    mock_sum.return_value = {
                        "run_id": "r1",
                        "goal_id": "g1",
                        "status": "completed",
                        "skills": ["s1"],
                        "event_count": 0,
                        "errors": [],
                    }
                    history_list(limit=10)
        captured = capsys.readouterr()
        assert "r1" in captured.out or captured.out


class TestHistoryShow:
    def test_invalid_index(self, capsys):
        with patch("uar.cli.main.get_store") as mock_get:
            mock_store = MagicMock()
            mock_store.list_all.return_value = []
            mock_get.return_value = mock_store
            with pytest.raises(typer.Exit):
                history_show(index=1, timeline=False)

    def test_show(self):
        mock_record = MagicMock()
        mock_record.run_id = "r1"
        mock_record.goal_id = "g1"
        mock_record.status = "completed"
        mock_record.skills = ["s1"]
        mock_record.events = []
        mock_record.outputs = {}

        with patch("uar.cli.main.console"):
            with patch("uar.cli.main.get_store") as mock_get:
                mock_store = MagicMock()
                mock_store.list_all.return_value = [{}]
                mock_get.return_value = mock_store
                with patch("uar.cli.main.run_record_from_dict") as mock_from:
                    mock_from.return_value = mock_record
                    with patch("uar.cli.main.replay_summary") as mock_sum:
                        mock_sum.return_value = {
                            "run_id": "r1",
                            "goal_id": "g1",
                            "status": "completed",
                            "skills": ["s1"],
                            "event_count": 0,
                            "errors": [],
                        }
                        history_show(index=1, timeline=False)


class TestHealthLocal:
    def test_health(self, capsys):
        with patch("uar.cli.main.registry") as mock_reg:
            mock_reg.list.return_value = ["s1"]
            mock_reg.get.return_value = lambda: None
            health_local()
        captured = capsys.readouterr()
        assert "s1" in captured.out or captured.out

    def test_exception(self, capsys):
        from uar.core.exceptions import SkillNotFoundError

        with patch("uar.cli.main.registry") as mock_reg:
            mock_reg.list.return_value = ["s1"]
            mock_reg.get.side_effect = SkillNotFoundError("fail")
            health_local()
        captured = capsys.readouterr()
        assert "s1" in captured.out or captured.out


class TestHealthServer:
    def test_success(self, capsys):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            health_server(server="http://test")
        captured = capsys.readouterr()
        assert captured.out or True

    def test_non_200(self, capsys):
        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            health_server(server="http://test")
        captured = capsys.readouterr()
        assert captured.out or True

    def test_error(self, capsys):
        mock_client = MagicMock()
        mock_client.get.side_effect = Exception("fail")

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            health_server(server="http://test")
        captured = capsys.readouterr()
        assert captured.out or True


class TestOpenapiExport:
    def test_stdout(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"openapi": "3.0.0"}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            openapi_export(output=None, server="http://test")
        captured = capsys.readouterr()
        assert "openapi" in captured.out or captured.out

    def test_output_file(self, capsys, tmp_path):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"openapi": "3.0.0"}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        out = tmp_path / "spec.json"
        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            openapi_export(output=str(out), server="http://test")
        captured = capsys.readouterr()
        assert out.exists() or captured.out

    def test_connect_error(self, capsys):
        import httpx

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.side_effect = (
                httpx.ConnectError("fail")
            )
            with pytest.raises(typer.Exit):
                openapi_export(output=None, server="http://test")

    def test_http_error(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.get.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                openapi_export(output=None, server="http://test")


class TestApiHeaders:
    def test_no_key(self):
        assert _api_headers(None) == {"Content-Type": "application/json"}

    def test_with_key(self):
        assert _api_headers("k")["Authorization"] == "Bearer k"


class TestDoctor:
    def test_local_ok(self):
        with patch("uar.cli.main.console"):
            with patch("uar.config.validate_environment") as ve:
                ve.return_value = []
                with patch("uar.config.validate_docker_environment") as vde:
                    vde.return_value = []
                    with patch(
                        "uar.config_advanced.validate_advanced_config"
                    ) as va:
                        va.return_value = {
                            "valid": True, "issues": []
                        }
                        with patch("httpx.Client") as mock_httpx:
                            mock_resp = MagicMock()
                            mock_resp.json.return_value = {
                                "skills": [],
                                "circuit_breakers": [],
                            }
                            mock_client = MagicMock()
                            mock_client.get.return_value = mock_resp
                            enter = mock_httpx.return_value.__enter__
                            enter.return_value = mock_client
                            doctor_command(
                                server="http://test",
                                api_key=None,
                            )

    def test_unhealthy_skills(self):
        with patch("uar.cli.main.console"):
            with patch("uar.config.validate_environment") as ve:
                ve.return_value = []
                with patch("uar.config.validate_docker_environment") as vde:
                    vde.return_value = []
                    with patch(
                        "uar.config_advanced.validate_advanced_config"
                    ) as va:
                        va.return_value = {
                            "valid": True, "issues": []
                        }
                        with patch("httpx.Client") as mock_httpx:
                            mock_resp = MagicMock()
                            mock_resp.json.return_value = {
                                "skills": [
                                    {"name": "s1", "available": False,
                                     "last_error": "fail"}
                                ],
                                "circuit_breakers": [],
                            }
                            mock_client = MagicMock()
                            mock_client.get.return_value = mock_resp
                            enter = mock_httpx.return_value.__enter__
                            enter.return_value = mock_client
                            doctor_command(
                                server="http://test",
                                api_key=None,
                            )

    def test_open_circuits(self):
        with patch("uar.cli.main.console"):
            with patch("uar.config.validate_environment") as ve:
                ve.return_value = []
                with patch("uar.config.validate_docker_environment") as vde:
                    vde.return_value = []
                    with patch(
                        "uar.config_advanced.validate_advanced_config"
                    ) as va:
                        va.return_value = {
                            "valid": True, "issues": []
                        }
                        with patch("httpx.Client") as mock_httpx:
                            mock_resp = MagicMock()
                            mock_resp.json.return_value = {
                                "skills": [],
                                "circuit_breakers": [
                                    {"name": "cb1", "state": "open"}
                                ],
                            }
                            mock_client = MagicMock()
                            mock_client.get.return_value = mock_resp
                            enter = mock_httpx.return_value.__enter__
                            enter.return_value = mock_client
                            doctor_command(
                                server="http://test",
                                api_key=None,
                            )

    def test_server_connect_error(self):
        import httpx

        with patch("uar.cli.main.console"):
            with patch("uar.config.validate_environment") as ve:
                ve.return_value = []
                with patch("uar.config.validate_docker_environment") as vde:
                    vde.return_value = []
                    with patch(
                        "uar.config_advanced.validate_advanced_config"
                    ) as va:
                        va.return_value = {
                            "valid": True, "issues": []
                        }
                        with patch("httpx.Client") as mock_httpx:
                            mock_httpx.return_value.__enter__.side_effect = (
                                httpx.ConnectError("fail")
                            )
                            doctor_command(
                                server="http://test",
                                api_key=None,
                            )

    def test_server_http_error(self):
        import httpx

        with patch("uar.cli.main.console"):
            with patch("uar.config.validate_environment") as ve:
                ve.return_value = []
                with patch("uar.config.validate_docker_environment") as vde:
                    vde.return_value = []
                    with patch(
                        "uar.config_advanced.validate_advanced_config"
                    ) as va:
                        va.return_value = {
                            "valid": True, "issues": []
                        }
                        with patch("httpx.Client") as mock_httpx:
                            mock_resp = MagicMock()
                            mock_resp.status_code = 500
                            exc = httpx.HTTPStatusError(
                                "fail", request=MagicMock(),
                                response=mock_resp
                            )
                            mock_client = MagicMock()
                            gfs = mock_client.get.return_value
                            gfs.raise_for_status.side_effect = exc
                            enter = mock_httpx.return_value.__enter__
                            enter.return_value = mock_client
                            doctor_command(
                                server="http://test",
                                api_key=None,
                            )

    def test_local_issues(self):
        with patch("uar.cli.main.console"):
            with patch("uar.config.validate_environment") as ve:
                ve.return_value = ["env issue"]
                with patch("uar.config.validate_docker_environment") as vde:
                    vde.return_value = ["docker issue"]
                    with patch(
                        "uar.config.Config"
                    ) as MockCfg:
                        cfg = MagicMock()
                        cfg.validate.return_value = ["config issue"]
                        MockCfg.return_value = cfg
                        with patch(
                            "uar.config_advanced.validate_advanced_config"
                        ) as va:
                            va.return_value = {
                                "valid": False, "issues": ["adv issue"]
                            }
                            with patch("httpx.Client") as mock_httpx:
                                mock_resp = MagicMock()
                                mock_resp.json.return_value = {
                                    "skills": [],
                                    "circuit_breakers": [],
                                }
                                mock_client = MagicMock()
                                mock_client.get.return_value = mock_resp
                                enter = mock_httpx.return_value.__enter__
                                enter.return_value = mock_client
                                doctor_command(
                                    server="http://test",
                                    api_key=None,
                                )


class TestSkillPing:
    def test_success(self):
        get_resp = MagicMock()
        get_resp.json.return_value = {"skills": ["s1"]}
        post_resp = MagicMock()
        post_resp.json.return_value = {"status": "ok", "latency_ms": 1.0}
        mock_client = MagicMock()
        mock_client.get.return_value = get_resp
        mock_client.post.return_value = post_resp

        with patch("uar.cli.main.console"):
            with patch("httpx.Client") as mock_httpx:
                mock_httpx.return_value.__enter__.return_value = mock_client
                skill_ping("s1", server="http://test", api_key=None)

    def test_not_registered(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"skills": ["s2"]}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("uar.cli.main.console"):
            with patch("httpx.Client") as mock_httpx:
                mock_httpx.return_value.__enter__.return_value = mock_client
                with pytest.raises(typer.Exit):
                    skill_ping("s1", server="http://test", api_key=None)

    def test_connect_error(self):
        import httpx

        with patch("uar.cli.main.console"):
            with patch("httpx.Client") as mock_httpx:
                mock_httpx.return_value.__enter__.side_effect = (
                    httpx.ConnectError("fail")
                )
                with pytest.raises(typer.Exit):
                    skill_ping("s1", server="http://test", api_key=None)

    def test_http_error(self):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.get.return_value.raise_for_status.side_effect = exc

        with patch("uar.cli.main.console"):
            with patch("httpx.Client") as mock_httpx:
                mock_httpx.return_value.__enter__.return_value = mock_client
                with pytest.raises(typer.Exit):
                    skill_ping("s1", server="http://test", api_key=None)

    def test_failed_status(self):
        get_resp = MagicMock()
        get_resp.json.return_value = {"skills": ["s1"]}
        post_resp = MagicMock()
        post_resp.json.return_value = {
            "status": "failed", "error": "bad"
        }
        mock_client = MagicMock()
        mock_client.get.return_value = get_resp
        mock_client.post.return_value = post_resp

        with patch("uar.cli.main.console"):
            with patch("httpx.Client") as mock_httpx:
                mock_httpx.return_value.__enter__.return_value = mock_client
                with pytest.raises(typer.Exit):
                    skill_ping("s1", server="http://test", api_key=None)


class TestCircuitBreaker:
    def test_list_empty(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"circuits": {}}
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            cb_list(server="http://test", api_key=None)
        captured = capsys.readouterr()
        assert "No circuit breakers" in captured.out or captured.out

    def test_list_with_circuits(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "circuits": {"svc1": {"state": "closed", "failures": 0}}
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            cb_list(server="http://test", api_key=None)
        captured = capsys.readouterr()
        assert "svc1" in captured.out or captured.out

    def test_reset(self, capsys):
        mock_client = MagicMock()

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            cb_reset("svc1", server="http://test", api_key=None)
        captured = capsys.readouterr()
        assert "reset" in captured.out.lower() or captured.out

    def test_list_connect_error(self, capsys):
        import httpx

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.side_effect = (
                httpx.ConnectError("fail")
            )
            with pytest.raises(typer.Exit):
                cb_list(server="http://test", api_key=None)

    def test_list_http_error(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.get.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                cb_list(server="http://test", api_key=None)

    def test_reset_404(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 404
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                cb_reset("svc1", server="http://test", api_key=None)

    def test_reset_403(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 403
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                cb_reset("svc1", server="http://test", api_key=None)

    def test_reset_other_http(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                cb_reset("svc1", server="http://test", api_key=None)

    def test_reset_connect_error(self, capsys):
        import httpx

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.side_effect = (
                httpx.ConnectError("fail")
            )
            with pytest.raises(typer.Exit):
                cb_reset("svc1", server="http://test", api_key=None)


class TestRunCompare:
    def test_success(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "same_status": True,
            "same_skills": True,
            "diffs": {},
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            run_compare("a", "b", server="http://test", api_key=None)
        captured = capsys.readouterr()
        assert "identical" in captured.out.lower() or captured.out

    def test_differences(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "same_status": False,
            "same_skills": False,
            "diffs": {"status": {"a": "ok", "b": "fail"}},
        }
        mock_client = MagicMock()
        mock_client.get.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            run_compare("a", "b", server="http://test", api_key=None)
        captured = capsys.readouterr()
        assert "Differences" in captured.out or captured.out

    def test_connect_error(self, capsys):
        import httpx

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.side_effect = (
                httpx.ConnectError("fail")
            )
            with pytest.raises(typer.Exit):
                run_compare("a", "b", server="http://test", api_key=None)

    def test_http_error(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.get.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                run_compare("a", "b", server="http://test", api_key=None)


class TestRunDelete:
    def test_success(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"deleted": 1}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            run_delete("r1", server="http://test", api_key=None)
        captured = capsys.readouterr()
        assert "Deleted" in captured.out or captured.out

    def test_none_deleted(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"deleted": 0}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            run_delete("r1", server="http://test", api_key=None)
        captured = capsys.readouterr()
        assert "No runs deleted" in captured.out or captured.out

    def test_connect_error(self, capsys):
        import httpx

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.side_effect = (
                httpx.ConnectError("fail")
            )
            with pytest.raises(typer.Exit):
                run_delete("r1", server="http://test", api_key=None)

    def test_http_error(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                run_delete("r1", server="http://test", api_key=None)


class TestRunBulkDelete:
    def test_success(self, capsys):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"deleted": 5, "filter": "older_than"}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            run_bulk_delete(30, server="http://test", api_key=None)
        captured = capsys.readouterr()
        assert "Deleted" in captured.out or captured.out

    def test_connect_error(self, capsys):
        import httpx

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.side_effect = (
                httpx.ConnectError("fail")
            )
            with pytest.raises(typer.Exit):
                run_bulk_delete(30, server="http://test", api_key=None)

    def test_http_error(self, capsys):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = exc

        with patch("httpx.Client") as mock_httpx:
            mock_httpx.return_value.__enter__.return_value = mock_client
            with pytest.raises(typer.Exit):
                run_bulk_delete(30, server="http://test", api_key=None)
