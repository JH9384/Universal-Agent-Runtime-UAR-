"""Tests for uar.skills.atomic_lang_model."""

from unittest.mock import MagicMock, patch

from uar.skills.atomic_lang_model import (
    _get_http_client,
    _get_service_url,
    _call_alm,
    _mock_alm_response,
    alm_analyze,
    alm_generate,
    alm_verify,
)


class TestGetHttpClient:
    def test_no_httpx(self):
        with patch("uar.skills.atomic_lang_model.HTTPX_AVAILABLE", False):
            assert _get_http_client() is None

    def test_creates_client(self):
        with patch("uar.skills.atomic_lang_model.HTTPX_AVAILABLE", True):
            with patch("uar.skills.atomic_lang_model.httpx") as mock_httpx:
                mock_client = MagicMock()
                mock_httpx.Client.return_value = mock_client
                with patch(
                    "uar.skills.atomic_lang_model._http_client", None
                ):
                    client = _get_http_client()
                assert client is mock_client


class TestGetServiceUrl:
    def test_default(self):
        with patch("os.getenv", return_value=None):
            url = _get_service_url()
        assert url == "http://localhost:5001/api/v1"

    def test_env_override(self):
        with patch("os.getenv", return_value="http://custom:8080"):
            url = _get_service_url()
        assert url == "http://custom:8080"

    def test_ctx_override(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"alm_service_url": "http://ctx:9000"}
        with patch("os.getenv", return_value=None):
            url = _get_service_url(ctx)
        assert url == "http://ctx:9000"

    def test_invalid_scheme(self):
        with patch("os.getenv", return_value="ftp://bad"):
            url = _get_service_url()
        assert url == "http://localhost:5001/api/v1"


class TestCallAlm:
    def test_no_client_uses_mock(self):
        with patch("uar.skills.atomic_lang_model.HTTPX_AVAILABLE", False):
            result = _call_alm("analyze", {"grammar_spec": "test"})
        assert result["status"] == "success"

    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"status": "ok"}
        mock_client = MagicMock()
        mock_client.post.return_value = mock_resp
        with patch(
            "uar.skills.atomic_lang_model._get_http_client"
        ) as get_client:
            get_client.return_value = mock_client
            result = _call_alm("analyze", {"a": 1})
        assert result["status"] == "ok"

    def test_http_error(self):
        import httpx

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.json.return_value = {"error": "fail"}
        exc = httpx.HTTPStatusError(
            "fail", request=MagicMock(), response=mock_resp
        )
        mock_client = MagicMock()
        mock_client.post.return_value.raise_for_status.side_effect = exc
        with patch(
            "uar.skills.atomic_lang_model._get_http_client"
        ) as get_client:
            get_client.return_value = mock_client
            result = _call_alm("analyze", {"a": 1})
        assert result["status"] == "error"

    def test_timeout(self):
        import httpx

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.TimeoutException("timeout")
        with patch(
            "uar.skills.atomic_lang_model._get_http_client"
        ) as get_client:
            get_client.return_value = mock_client
            result = _call_alm("analyze", {"a": 1})
        assert result["status"] == "error"
        assert "timeout" in result["error"].lower()

    def test_connect_error(self):
        import httpx

        mock_client = MagicMock()
        mock_client.post.side_effect = httpx.ConnectError("conn fail")
        with patch(
            "uar.skills.atomic_lang_model._get_http_client"
        ) as get_client:
            get_client.return_value = mock_client
            result = _call_alm("analyze", {"a": 1})
        assert result["status"] == "error"
        assert "connection" in result["error"].lower()


class TestMockAlmResponse:
    def test_analyze(self):
        result = _mock_alm_response("analyze", {"grammar_spec": "test"})
        assert result["status"] == "success"

    def test_analyze_recursive(self):
        result = _mock_alm_response(
            "analyze", {"grammar_spec": "recursive BNF"}
        )
        assert "recursion" in result["analysis"].lower()

    def test_generate(self):
        result = _mock_alm_response("generate", {"prefix": "x", "count": 3})
        assert len(result["tokens"]) == 3

    def test_generate_student(self):
        result = _mock_alm_response(
            "generate", {"prefix": "student", "count": 5}
        )
        assert "student" in result["tokens"]

    def test_verify_valid(self):
        result = _mock_alm_response("verify", {"text": "student left"})
        assert result["valid"] is True

    def test_verify_invalid(self):
        result = _mock_alm_response("verify", {"text": "bad"})
        assert result["valid"] is False

    def test_unknown_endpoint(self):
        result = _mock_alm_response("unknown", {})
        assert result["status"] == "error"


class TestAlmAnalyze:
    def test_no_grammar(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        result = alm_analyze(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"grammar_spec": "BNF"}
        with patch(
            "uar.skills.atomic_lang_model._call_alm"
        ) as mock_call:
            mock_call.return_value = {"analysis": "ok"}
            result = alm_analyze(ctx)
        assert result["status"] == "completed"
        assert result["grammar_spec"] == "BNF"


class TestAlmGenerate:
    def test_no_prefix(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        result = alm_generate(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"prefix": "hello", "count": 3}
        with patch(
            "uar.skills.atomic_lang_model._call_alm"
        ) as mock_call:
            mock_call.return_value = {"tokens": ["a", "b", "c"]}
            result = alm_generate(ctx)
        assert result["status"] == "completed"
        assert result["tokens"] == ["a", "b", "c"]


class TestAlmVerify:
    def test_no_text(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        result = alm_verify(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"text": "hello"}
        with patch(
            "uar.skills.atomic_lang_model._call_alm"
        ) as mock_call:
            mock_call.return_value = {"valid": True, "proof_id": "p1"}
            result = alm_verify(ctx)
        assert result["status"] == "completed"
        assert result["valid"] is True
