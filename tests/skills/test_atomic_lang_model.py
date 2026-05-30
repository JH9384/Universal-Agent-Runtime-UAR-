"""Tests for uar.skills.atomic_lang_model missed branches."""

from unittest.mock import MagicMock, patch

from uar.skills.atomic_lang_model import (
    _close_http_client,
    _get_http_client,
    _get_service_url,
    _call_alm,
)


class TestGetHttpClient:
    def test_creates_when_none(self):
        with patch("uar.skills.atomic_lang_model._http_client", None):
            client = _get_http_client()
            assert client is not None

    def test_reuses_existing(self):
        mock_client = MagicMock()
        with patch("uar.skills.atomic_lang_model._http_client", mock_client):
            client = _get_http_client()
            assert client is mock_client


class TestCloseHttpClient:
    def test_close_exception(self):
        mock_client = MagicMock()
        mock_client.close.side_effect = RuntimeError("close failed")
        with patch("uar.skills.atomic_lang_model._http_client", mock_client):
            _close_http_client()


class TestGetServiceUrl:
    def test_invalid_scheme(self):
        class FakeGoal:
            metadata = {"alm_service_url": "ftp://bad"}

        class FakeCtx:
            goal = FakeGoal()

        url = _get_service_url(FakeCtx())
        assert url == "http://localhost:5001/api/v1"


class TestCallAlm:
    def test_httpstatus_error_bad_json(self):
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.json.side_effect = ValueError("bad json")
        mock_response.text = "error"

        mock_exc = httpx.HTTPStatusError(
            "Server error", request=MagicMock(), response=mock_response
        )

        mock_client = MagicMock()
        mock_client.post.side_effect = mock_exc

        with patch(
            "uar.skills.atomic_lang_model._get_http_client",
            return_value=mock_client,
        ):
            result = _call_alm("analyze", {"grammar_spec": "x"})
            assert result["status"] == "error"
