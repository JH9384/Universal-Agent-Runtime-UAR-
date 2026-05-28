"""Tests for graphrag_skills helper functions.

The skills themselves call external CLIs (graphrag, ollama) so we test
pure-Python helpers: workspace management, schema/versioning, input
staging, CLI runner, and path validation.
"""

import os
from unittest.mock import patch, MagicMock

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.graphrag_skills import (
    _ensure_workspace,
    _get_graph_schema_version,
    _set_graph_schema_version,
    _check_schema_compatibility,
    _stage_inputs,
    _run_cli_impl,
    _write_settings,
    graphrag_init,
    graphrag_index,
    graphrag_query,
    GRAPH_SCHEMA_VERSION,
)


def _make_ctx(metadata: dict = None) -> PipelineContext:
    meta = metadata or {}
    goal = GoalSpec(
        id="test",
        user_intent="test",
        objective=meta.get("objective", "test query"),
        metadata=meta,
    )
    return PipelineContext(goal=goal)


class TestWorkspaceHelpers:
    """Workspace setup and schema helpers."""

    def test_ensure_workspace_creates_dirs(self, tmp_path, monkeypatch):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            root = _ensure_workspace()
            assert (root / "input").exists()
            assert (root / "output").exists()
            assert (root / "cache").exists()
            assert (root / "logs").exists()
            assert (root / "prompts").exists()

    def test_ensure_workspace_writes_settings(self, tmp_path, monkeypatch):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            root = _ensure_workspace()
            assert (root / "settings.yaml").exists()
            content = (root / "settings.yaml").read_text()
            assert "openai_chat" in content
            assert "cl100k_base" in content

    def test_ensure_workspace_writes_env_file(self, tmp_path, monkeypatch):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            root = _ensure_workspace()
            env_file = root / ".env"
            assert env_file.exists()
            assert "GRAPHRAG_API_KEY" in env_file.read_text()

    def test_graphrag_init_skill(self, tmp_path, monkeypatch):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            result = graphrag_init(_make_ctx())
            assert result["status"] == "completed"
            assert result["schema_version"] == GRAPH_SCHEMA_VERSION
            assert "workspace" in result


class TestSchemaVersioning:
    """Schema version read/write and compatibility checks."""

    def test_get_schema_version_unknown(self, tmp_path):
        assert _get_graph_schema_version(tmp_path) == "unknown"

    def test_set_and_get_schema_version(self, tmp_path):
        _set_graph_schema_version(tmp_path, "v2")
        assert _get_graph_schema_version(tmp_path) == "v2"

    def test_schema_compatibility_new_graph(self, tmp_path):
        ok, msg = _check_schema_compatibility(tmp_path)
        assert ok is True
        assert msg == ""

    def test_schema_compatibility_matching(self, tmp_path):
        _set_graph_schema_version(tmp_path, GRAPH_SCHEMA_VERSION)
        ok, msg = _check_schema_compatibility(tmp_path)
        assert ok is True
        assert msg == ""

    def test_schema_compatibility_mismatch(self, tmp_path):
        _set_graph_schema_version(tmp_path, "v0-old")
        ok, msg = _check_schema_compatibility(tmp_path)
        assert ok is False
        assert "mismatch" in msg.lower()


class TestInputStaging:
    """Document staging from source to graphrag input/."""

    def test_stage_single_file(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "doc.txt").write_text("Hello world")
        inp = tmp_path / "input"
        count = _stage_inputs(src, inp)
        assert count == 1
        # _stage_inputs appends .txt to the filename
        assert (inp / "doc.txt.txt").exists()
        assert (inp / "doc.txt.txt").read_text() == "Hello world"

    def test_stage_skips_unsupported_extensions(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        (src / "good.txt").write_text("ok")
        (src / "bad.exe").write_text("virus")
        inp = tmp_path / "input"
        count = _stage_inputs(src, inp)
        assert count == 1
        assert (inp / "good.txt.txt").exists()
        assert not (inp / "bad.exe.txt").exists()

    def test_stage_nested_directories(self, tmp_path):
        src = tmp_path / "source"
        sub = src / "sub"
        sub.mkdir(parents=True)
        (src / "a.txt").write_text("A")
        (sub / "b.md").write_text("B")
        inp = tmp_path / "input"
        count = _stage_inputs(src, inp)
        assert count == 2

    def test_stage_empty_source(self, tmp_path):
        src = tmp_path / "source"
        src.mkdir()
        inp = tmp_path / "input"
        count = _stage_inputs(src, inp)
        assert count == 0

    def test_stage_single_file_path(self, tmp_path):
        src_file = tmp_path / "single.txt"
        src_file.write_text("solo")
        inp = tmp_path / "input"
        count = _stage_inputs(src_file, inp)
        assert count == 1


class TestCliRunner:
    """CLI runner with mocked subprocess."""

    def test_run_cli_success(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="ok", stderr=""
            )
            result = _run_cli_impl(["echo", "hi"], tmp_path, timeout=5)
            assert result["returncode"] == 0
            assert result["stdout"] == "ok"

    def test_run_cli_failure(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(
                returncode=1, stdout="", stderr="error"
            )
            result = _run_cli_impl(["false"], tmp_path, timeout=5)
            assert result["returncode"] == 1
            assert result["stderr"] == "error"

    def test_run_cli_timeout(self, tmp_path):
        from subprocess import TimeoutExpired

        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = TimeoutExpired("cmd", 5)
            result = _run_cli_impl(["sleep", "10"], tmp_path, timeout=1)
            assert result["returncode"] == -1
            assert "timeout" in result["stderr"].lower()

    def test_run_cli_not_found(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.side_effect = FileNotFoundError()
            result = _run_cli_impl(["graphrag"], tmp_path, timeout=5)
            assert result["returncode"] == -1
            assert "not found" in result["stderr"].lower()

    def test_run_cli_output_truncation(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            huge = "x" * 50000
            mock_run.return_value = MagicMock(
                returncode=0, stdout=huge, stderr=huge
            )
            result = _run_cli_impl(["cat"], tmp_path, timeout=5)
            assert len(result["stdout"]) <= 20001
            assert len(result["stderr"]) <= 20001


class TestGraphragQueryValidation:
    """graphrag_query without actual CLI calls."""

    def test_query_no_workspace(self, tmp_path):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            result = graphrag_query(_make_ctx())
            assert result["status"] == "failed"
            assert "No GraphRAG workspace" in result["error"]

    def test_query_empty_query(self, tmp_path):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            _ensure_workspace()
            result = graphrag_query(
                _make_ctx({"graphrag_query": "", "objective": ""})
            )
            assert result["status"] == "failed"
            assert "Empty query" in result["error"]

    def test_query_default_method(self, tmp_path):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            _ensure_workspace()
            with patch(
                "uar.skills.graphrag_skills._run_cli",
                return_value={
                    "returncode": 0, "stdout": "answer", "stderr": "",
                },
            ):
                result = graphrag_query(
                    _make_ctx({"graphrag_query": "test"})
                )
            assert result["method"] == "local"

    def test_query_global_method(self, tmp_path):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            _ensure_workspace()
            with patch(
                "uar.skills.graphrag_skills._run_cli",
                return_value={"returncode": 0, "stdout": "", "stderr": ""},
            ):
                result = graphrag_query(
                    _make_ctx({
                        "graphrag_query": "test",
                        "graphrag_method": "global",
                    })
                )
            assert result["method"] == "global"

    def test_query_invalid_method_fallback(self, tmp_path):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            _ensure_workspace()
            with patch(
                "uar.skills.graphrag_skills._run_cli",
                return_value={"returncode": 0, "stdout": "", "stderr": ""},
            ):
                result = graphrag_query(
                    _make_ctx({
                        "graphrag_query": "test",
                        "graphrag_method": "invalid",
                    })
                )
            assert result["method"] == "local"

    def test_query_success_parsing(self, tmp_path):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            _ensure_workspace()
            with patch(
                "uar.skills.graphrag_skills._run_cli",
                return_value={
                    "returncode": 0,
                    "stdout": "SUCCESS: the answer is 42",
                    "stderr": "",
                },
            ):
                result = graphrag_query(
                    _make_ctx({"graphrag_query": "what is the answer"})
                )
            assert result["status"] == "completed"
            assert "the answer is 42" in result["response"]


class TestGraphragIndexValidation:
    """graphrag_index validation paths."""

    def test_index_missing_input_path(self, tmp_path, monkeypatch):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            with patch("uar.skills.graphrag_skills.ALLOWED_ROOT", tmp_path):
                _ensure_workspace()
                with patch(
                    "uar.skills.graphrag_skills._check_ollama_health",
                    return_value=(True, ""),
                ):
                    result = graphrag_index(
                        _make_ctx({
                            "input_path": str(tmp_path / "nonexistent"),
                        })
                    )
                assert result["status"] == "failed"
                assert "does not exist" in result["error"]

    def test_index_empty_directory(self, tmp_path, monkeypatch):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            with patch("uar.skills.graphrag_skills.ALLOWED_ROOT", tmp_path):
                _ensure_workspace()
                empty_dir = tmp_path / "empty"
                empty_dir.mkdir()
                with patch(
                    "uar.skills.graphrag_skills._check_ollama_health",
                    return_value=(True, ""),
                ):
                    result = graphrag_index(
                        _make_ctx({"input_path": str(empty_dir)})
                    )
                assert result["status"] == "failed"
                assert "No ingestible files" in result["error"]

    def test_index_no_files_staged(self, tmp_path, monkeypatch):
        with patch.dict(os.environ, {"UAR_GRAPHRAG_ROOT": str(tmp_path)}):
            with patch("uar.skills.graphrag_skills.ALLOWED_ROOT", tmp_path):
                _ensure_workspace()
                bad_dir = tmp_path / "bad"
                bad_dir.mkdir()
                (bad_dir / "file.exe").write_text("data")
                with patch(
                    "uar.skills.graphrag_skills._check_ollama_health",
                    return_value=(True, ""),
                ):
                    result = graphrag_index(
                        _make_ctx({"input_path": str(bad_dir)})
                    )
                assert result["status"] == "failed"
                assert "No ingestible files" in result["error"]


class TestWriteSettings:
    """Settings YAML generation."""

    def test_settings_includes_model_config(self, tmp_path):
        with patch.dict(
            os.environ,
            {
                "OLLAMA_HOST": "http://host:8080",
                "OLLAMA_MODEL": "custom-model",
            },
        ):
            path = _write_settings(tmp_path)
            content = path.read_text()
            assert "http://host:8080/v1" in content
            assert "custom-model" in content
            assert "openai_chat" in content

    def test_settings_defaults(self, tmp_path):
        with patch.dict(os.environ, {}, clear=True):
            path = _write_settings(tmp_path)
            content = path.read_text()
            assert "http://127.0.0.1:11434/v1" in content
            assert "llama3.2:3b" in content
            assert "nomic-embed-text" in content
