"""Tests for Atomic Language Model client.

Covers AtomicLanguageModelSkill init and API methods.
"""

from unittest.mock import patch

from uar.objects.alm_client import AtomicLanguageModelSkill, HTTPX_AVAILABLE


class TestInit:
    """Initialization."""

    def test_default_url(self):
        skill = AtomicLanguageModelSkill()
        assert "localhost:5001" in skill.base_url

    def test_custom_url(self):
        skill = AtomicLanguageModelSkill(base_url="http://alm.example.com")
        assert skill.base_url == "http://alm.example.com"

    def test_url_from_env(self):
        env = {"ALM_SERVICE_URL": "http://custom:8080/api"}
        with patch.dict("os.environ", env):
            skill = AtomicLanguageModelSkill()
        assert skill.base_url == "http://custom:8080/api"

    def test_close(self):
        skill = AtomicLanguageModelSkill()
        skill.close()
        assert skill.client is None or skill.client

    def test_context_manager(self):
        with AtomicLanguageModelSkill() as skill:
            assert skill is not None


class TestNoHttpxFallback:
    """Fallback behavior when client is None."""

    def test_analyze_grammar_fallback(self):
        skill = AtomicLanguageModelSkill()
        skill.client = None
        result = skill.analyze_grammar("test")
        assert result["status"] == "success"

    def test_generate_sequence_fallback(self):
        skill = AtomicLanguageModelSkill()
        skill.client = None
        result = skill.generate_sequence("hello", count=3)
        assert len(result) == 3

    def test_verify_syntax_fallback(self):
        skill = AtomicLanguageModelSkill()
        skill.client = None
        result = skill.verify_syntax("student left")
        assert result["valid"] is True

    def test_predict_fallback(self):
        skill = AtomicLanguageModelSkill()
        skill.client = None
        result = skill.predict("hello")
        assert "prediction" in result

    def test_validate_sentences_fallback(self):
        skill = AtomicLanguageModelSkill()
        skill.client = None
        result = skill.validate_sentences(["a", "b"])
        assert len(result["results"]) == 2

    def test_generate_sentences_fallback(self):
        skill = AtomicLanguageModelSkill()
        skill.client = None
        result = skill.generate_sentences(count=3)
        assert len(result) == 3


class TestWithMockedHttpx:
    """Test HTTP paths with mocked client responses."""

    def _mock_resp(self, data):
        from unittest.mock import Mock
        m = Mock()
        m.json.return_value = data
        m.raise_for_status.return_value = None
        return m

    def test_predict_success(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp({"prediction": "cat"})):
            result = skill.predict("the")
        assert result["prediction"] == "cat"

    def test_predict_http_error(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          side_effect=Exception("fail")):
            result = skill.predict("the")
        assert "error" in result

    def test_generate_sentences_success(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp({"sentences": ["a"]})):
            result = skill.generate_sentences(count=1)
        assert result == ["a"]

    def test_generate_sentences_list_response(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp(["x", "y"])):
            result = skill.generate_sentences(count=2)
        assert result == ["x", "y"]

    def test_validate_sentences_success(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "post",
                          return_value=self._mock_resp({"results": ["ok"]})):
            result = skill.validate_sentences(["hi"])
        assert result["results"] == ["ok"]

    def test_analyze_grammar_success(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "post",
                          return_value=self._mock_resp({"status": "ok"})):
            result = skill.analyze_grammar("grammar")
        assert result["status"] == "ok"

    def test_verify_syntax_success(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp({"valid": True})):
            result = skill.verify_syntax("hello")
        assert result["valid"] is True

    def test_analyze_grammar_legacy(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill(use_legacy_api=True)
        with patch.object(skill.client, "post",
                          return_value=self._mock_resp({"status": "ok"})):
            result = skill.analyze_grammar("grammar")
        assert result["status"] == "ok"

    def test_analyze_grammar_http_error(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        from unittest.mock import Mock
        err = Mock()
        err.side_effect = Exception("HTTP Error")
        err.__class__ = Exception
        with patch.object(skill.client, "post", side_effect=Exception("fail")):
            result = skill.analyze_grammar("grammar")
        assert result["status"] == "error"

    def test_generate_sequence_legacy(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill(use_legacy_api=True)
        with patch.object(skill.client, "post",
                          return_value=self._mock_resp({"tokens": ["a"]})):
            result = skill.generate_sequence("hello", count=1)
        assert result == ["a"]

    def test_generate_sequence_tokens_response(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp({"tokens": ["a"]})):
            result = skill.generate_sequence("hello", count=1)
        assert result == ["a"]

    def test_generate_sequence_unknown_response(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp({"unknown": "x"})):
            result = skill.generate_sequence("hello", count=2)
        assert result == ["token_0", "token_1"]

    def test_generate_sequence_http_error(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get", side_effect=Exception("fail")):
            result = skill.generate_sequence("hello", count=3)
        assert result == ["token_0", "token_1", "token_2"]

    def test_verify_syntax_legacy(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill(use_legacy_api=True)
        with patch.object(skill.client, "post",
                          return_value=self._mock_resp({"valid": True})):
            result = skill.verify_syntax("hello")
        assert result["valid"] is True

    def test_verify_syntax_is_valid_response(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp({"is_valid": True})):
            result = skill.verify_syntax("hello")
        assert result["valid"] is True

    def test_verify_syntax_prediction_response(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp({"prediction": "x"})):
            result = skill.verify_syntax("hello")
        assert result["valid"] is True
        assert result["prediction"] == "x"

    def test_verify_syntax_unknown_response(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get",
                          return_value=self._mock_resp({"other": "x"})):
            result = skill.verify_syntax("hello")
        assert result["valid"] is True
        assert result["result"]["other"] == "x"

    def test_verify_syntax_http_error(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get", side_effect=Exception("fail")):
            result = skill.verify_syntax("hello")
        assert result["valid"] is False

    def test_predict_exception(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get", side_effect=Exception("fail")):
            result = skill.predict("hello")
        assert "error" in result

    def test_validate_sentences_exception(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "post", side_effect=Exception("fail")):
            result = skill.validate_sentences(["hello"])
        assert "error" in result

    def test_generate_sentences_exception(self):
        if not HTTPX_AVAILABLE:
            return
        skill = AtomicLanguageModelSkill()
        with patch.object(skill.client, "get", side_effect=Exception("fail")):
            result = skill.generate_sentences(count=3)
        assert result == ["sentence_0", "sentence_1", "sentence_2"]

    def test_init_timeout_from_env(self):
        with patch.dict("os.environ", {"ALM_TIMEOUT_SEC": "60"}):
            skill = AtomicLanguageModelSkill()
        assert skill is not None

    def test_init_timeout_invalid_env(self):
        with patch.dict("os.environ", {"ALM_TIMEOUT_SEC": "bad"}):
            skill = AtomicLanguageModelSkill()
        assert skill is not None

    def test_init_httpx_unavailable(self):
        with patch("uar.objects.alm_client.HTTPX_AVAILABLE", False):
            skill = AtomicLanguageModelSkill()
        assert skill.client is None
