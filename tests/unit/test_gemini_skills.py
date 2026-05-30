"""Tests for uar.skills.gemini_skills."""

from unittest.mock import MagicMock, patch

from uar.skills.gemini_skills import (
    _get_client,
    gemini_chat,
    gemini_completion,
    gemini_embedding,
)


class TestGetClient:
    def test_no_package(self):
        with patch("uar.skills.gemini_skills.genai", None):
            assert _get_client() is None

    def test_no_api_key(self):
        with patch("uar.skills.gemini_skills.genai"):
            with patch("os.getenv", return_value=None):
                assert _get_client() is None

    def test_success(self):
        mock_genai = MagicMock()
        with patch("uar.skills.gemini_skills.genai", mock_genai):
            with patch("os.getenv", return_value="test_key"):
                client = _get_client()
                assert client is mock_genai


class TestGeminiChat:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.gemini_skills.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = gemini_chat(ctx)
        assert result["status"] == "error"

    def test_no_api_key(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value=None):
                result = gemini_chat(ctx)
        assert result["status"] == "failed"

    def test_no_messages(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value="key"):
                mock_model = MagicMock()
                mock_chat = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "hi"
                mock_response.usage_metadata = None
                mock_chat.send_message.return_value = mock_response
                mock_model.start_chat.return_value = mock_chat
                with patch("uar.skills.gemini_skills.genai") as mock_genai:
                    mock_genai.GenerativeModel.return_value = mock_model
                    mock_genai.GenerationConfig = MagicMock()
                    result = gemini_chat(ctx)
        assert result["status"] == "completed"
        assert result["message"] == "hi"

    def test_empty_response(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"messages": ["hello"]}
        ctx.goal.objective = ""
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value="key"):
                mock_model = MagicMock()
                mock_chat = MagicMock()
                mock_response = MagicMock()
                mock_response.text = ""
                mock_chat.send_message.return_value = mock_response
                mock_model.start_chat.return_value = mock_chat
                with patch("uar.skills.gemini_skills.genai") as mock_genai:
                    mock_genai.GenerativeModel.return_value = mock_model
                    mock_genai.GenerationConfig = MagicMock()
                    result = gemini_chat(ctx)
        assert result["status"] == "failed"

    def test_invalid_message_format(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"messages": [{"role": "user"}]}
        ctx.goal.objective = ""
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value="key"):
                with patch("uar.skills.gemini_skills.genai") as mock_genai:
                    mock_genai.GenerativeModel = MagicMock()
                    mock_genai.GenerationConfig = MagicMock()
                    result = gemini_chat(ctx)
        assert result["status"] == "failed"


class TestGeminiCompletion:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.gemini_skills.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = gemini_completion(ctx)
        assert result["status"] == "error"

    def test_no_api_key(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value=None):
                result = gemini_completion(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"prompt": "hello"}
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value="key"):
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = "world"
                mock_response.usage_metadata = None
                mock_model.generate_content.return_value = mock_response
                with patch("uar.skills.gemini_skills.genai") as mock_genai:
                    mock_genai.GenerativeModel.return_value = mock_model
                    mock_genai.GenerationConfig = MagicMock()
                    result = gemini_completion(ctx)
        assert result["status"] == "completed"
        assert result["text"] == "world"

    def test_empty_response(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value="key"):
                mock_model = MagicMock()
                mock_response = MagicMock()
                mock_response.text = ""
                mock_model.generate_content.return_value = mock_response
                with patch("uar.skills.gemini_skills.genai") as mock_genai:
                    mock_genai.GenerativeModel.return_value = mock_model
                    mock_genai.GenerationConfig = MagicMock()
                    result = gemini_completion(ctx)
        assert result["status"] == "failed"


class TestGeminiEmbedding:
    def test_missing_package(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch("uar.skills.gemini_skills.require_package") as req:
            req.return_value = {"status": "error", "error": "not installed"}
            result = gemini_embedding(ctx)
        assert result["status"] == "error"

    def test_no_api_key(self):
        ctx = MagicMock()
        ctx.goal.metadata = {}
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value=None):
                result = gemini_embedding(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        ctx = MagicMock()
        ctx.goal.metadata = {"text": "hello"}
        with patch(
            "uar.skills.gemini_skills.require_package",
            return_value=None,
        ):
            with patch("os.getenv", return_value="key"):
                with patch("uar.skills.gemini_skills.genai") as mock_genai:
                    mock_result = MagicMock()
                    mock_result.embedding = [0.1, 0.2]
                    mock_genai.embed_content.return_value = mock_result
                    result = gemini_embedding(ctx)
        assert result["status"] == "completed"
        assert result["embedding"] == [0.1, 0.2]
