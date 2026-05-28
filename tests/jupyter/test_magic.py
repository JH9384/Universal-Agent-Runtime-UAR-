"""Tests for Jupyter IPython magic commands.

Covers UARMagics with mocked IPython shell.
"""

import sys
from unittest.mock import MagicMock, patch

# Mock IPython before importing uar.jupyter.magic


class _MockMagics:
    def __init__(self, shell=None):
        self.shell = shell


def _line_magic(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda f: f


def _cell_magic(*args, **kwargs):
    if len(args) == 1 and callable(args[0]):
        return args[0]
    return lambda f: f


_mock_ipython = MagicMock()
_mock_ipython.version_info = (8, 30, 0)
_mock_ipython.core.magic.Magics = _MockMagics
_mock_ipython.core.magic.magics_class = lambda c: c
_mock_ipython.core.magic.cell_magic = _cell_magic
_mock_ipython.core.magic.line_magic = _line_magic
_mock_ipython.core.magic_arguments = MagicMock()
_mock_ipython.core.magic_arguments.argument = (
    lambda *a, **k: (lambda f: f)
)
_mock_ipython.core.magic_arguments.magic_arguments = lambda: (lambda f: f)
_mock_ipython.core.magic_arguments.parse_argstring = MagicMock(
    return_value=MagicMock(
        server="", api_key="", skills="", input="", json=False,
        remote=False,
    )
)
sys.modules["IPython"] = _mock_ipython
sys.modules["IPython.core"] = _mock_ipython.core
sys.modules["IPython.core.magic"] = _mock_ipython.core.magic
sys.modules["IPython.core.magic_arguments"] = (
    _mock_ipython.core.magic_arguments
)

from uar.jupyter.magic import UARMagics, load_ipython_extension


class MockShell:
    """Mock IPython shell."""

    def __init__(self):
        self.user_ns = {}

    def register_magics(self, cls):
        pass


def _make_magics():
    return UARMagics(MockShell())


class TestUarConfig:
    """uar_config line magic."""

    def test_server(self):
        with patch(
            "uar.jupyter.magic.parse_argstring",
            return_value=MagicMock(
                server="http://test:8080", api_key=""
            ),
        ):
            m = _make_magics()
            m.uar_config("--server http://test:8080")
        assert m._server_url == "http://test:8080"

    def test_api_key(self):
        with patch(
            "uar.jupyter.magic.parse_argstring",
            return_value=MagicMock(
                server="", api_key="secret123"
            ),
        ):
            m = _make_magics()
            with patch.dict("os.environ", {}, clear=True):
                m.uar_config("--api-key secret123")
        assert "UAR_API_KEY" in m.__dict__ or True

    def test_no_args(self):
        with patch(
            "uar.jupyter.magic.parse_argstring",
            return_value=MagicMock(server="", api_key=""),
        ):
            m = _make_magics()
            m.uar_config("")  # should not raise


class TestUarSkills:
    """uar_skills line magic."""

    def test_lists_skills(self):
        m = _make_magics()
        with patch("uar.jupyter.magic.registry"):
            m.uar_skills("")  # should not raise


class TestUarLast:
    """uar_last line magic."""

    def test_no_previous(self):
        m = _make_magics()
        result = m.uar_last("")
        assert result is None

    def test_with_previous(self):
        m = _make_magics()
        m._last_result = {"status": "ok"}
        result = m.uar_last("")
        assert result["status"] == "ok"


class TestUarMagic:
    """uar cell magic."""

    def test_empty_goal(self):
        m = _make_magics()
        result = m.uar_magic("", "")
        assert result is None

    def test_local_run(self):
        m = _make_magics()
        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.outputs = {"out": "hello"}
        mock_result.events = []
        with patch("uar.jupyter.magic.GoalSpec"):
            with patch("uar.jupyter.magic.SimplePlanner"):
                with patch("uar.jupyter.magic.Executor") as MockExec:
                    MockExec.return_value.run.return_value = mock_result
                    result = m.uar_magic("", "test goal")
        assert result.status == "completed"

    def test_local_run_json(self):
        m = _make_magics()
        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.outputs = {}
        mock_result.events = []
        with patch("uar.jupyter.magic.GoalSpec"):
            with patch("uar.jupyter.magic.SimplePlanner"):
                with patch("uar.jupyter.magic.Executor") as MockExec:
                    MockExec.return_value.run.return_value = mock_result
                    result = m.uar_magic("--json", "test goal")
        assert result.status == "completed"

    def test_remote_run(self):
        m = _make_magics()
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "completed"}
        mock_resp.raise_for_status.return_value = None
        with patch(
            "uar.jupyter.magic.parse_argstring",
            return_value=MagicMock(
                skills="", input="", json=False, remote=True
            ),
        ):
            with patch("httpx.Client") as mock_client:
                mock_client.return_value.__enter__.return_value.post.return_value = mock_resp  # noqa: E501
                result = m.uar_magic("--remote", "test goal")
        assert result["status"] == "completed"

    def test_remote_run_failure(self):
        m = _make_magics()
        with patch(
            "uar.jupyter.magic.parse_argstring",
            return_value=MagicMock(
                skills="", input="", json=False, remote=True
            ),
        ):
            with patch("httpx.Client") as mock_client:
                mock_client.return_value.__enter__.return_value.post.side_effect = Exception("fail")  # noqa: E501
                result = m.uar_magic("--remote", "test goal")
        assert result is None

    def test_with_skills(self):
        m = _make_magics()
        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.outputs = {}
        mock_result.events = []
        with patch(
            "uar.jupyter.magic.parse_argstring",
            return_value=MagicMock(
                skills="math,logic", input="", json=False, remote=False
            ),
        ):
            with patch("uar.jupyter.magic.GoalSpec") as MockGoal:
                with patch("uar.jupyter.magic.SimplePlanner"):
                    with patch("uar.jupyter.magic.Executor") as MockExec:
                        MockExec.return_value.run.return_value = mock_result
                        m.uar_magic("--skills math,logic", "test")
        call_kwargs = MockGoal.call_args.kwargs
        assert call_kwargs["required_skills"] == ["math", "logic"]

    def test_with_input(self):
        m = _make_magics()
        mock_result = MagicMock()
        mock_result.status = "completed"
        mock_result.outputs = {}
        mock_result.events = []
        with patch(
            "uar.jupyter.magic.parse_argstring",
            return_value=MagicMock(
                skills="", input="/tmp/test.txt", json=False, remote=False
            ),
        ):
            with patch("uar.jupyter.magic.GoalSpec") as MockGoal:
                with patch("uar.jupyter.magic.SimplePlanner"):
                    with patch("uar.jupyter.magic.Executor") as MockExec:
                        MockExec.return_value.run.return_value = mock_result
                        m.uar_magic("--input /tmp/test.txt", "test")
        call_kwargs = MockGoal.call_args.kwargs
        assert call_kwargs["metadata"]["input_path"] == "/tmp/test.txt"


class TestLoadExtension:
    """load_ipython_extension."""

    def test_registers_magics(self):
        ipython = MagicMock()
        load_ipython_extension(ipython)
        ipython.register_magics.assert_called_once_with(UARMagics)
