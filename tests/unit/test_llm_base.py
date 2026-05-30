"""Tests for uar.skills.llm_base."""

from unittest.mock import MagicMock, patch

from uar.skills.llm_base import (
    _clamp_timeout,
    make_client_getter,
    make_model_getter,
    make_temperature_getter,
    make_max_tokens_getter,
    _chat_skill,
    _completion_skill,
    _embedding_skill,
    register_openai_provider,
)


class TestClampTimeout:
    def test_default(self):
        assert _clamp_timeout(None) == 30

    def test_valid(self):
        assert _clamp_timeout("60") == 60

    def test_invalid(self):
        assert _clamp_timeout("abc") == 30

    def test_too_high(self):
        assert _clamp_timeout("500") == 300

    def test_too_low(self):
        assert _clamp_timeout("0") == 1


class TestMakeClientGetter:
    def test_none_module(self):
        getter = make_client_getter(
            module=None,
            api_key_env="TEST_KEY",
            timeout_env="TEST_TIMEOUT",
        )
        assert getter() is None

    def test_no_api_key(self):
        mod = MagicMock()
        getter = make_client_getter(
            module=mod,
            api_key_env="TEST_KEY",
            timeout_env="TEST_TIMEOUT",
        )
        with patch("os.getenv", return_value=None):
            assert getter() is None

    def test_success(self):
        mod = MagicMock()
        mock_client = MagicMock()
        mod.OpenAI.return_value = mock_client
        getter = make_client_getter(
            module=mod,
            api_key_env="TEST_KEY",
            timeout_env="TEST_TIMEOUT",
            base_url="http://test",
        )

        def _getenv(k, _d=None):
            return "key123" if k == "TEST_KEY" else None

        with patch("os.getenv", side_effect=_getenv):
            client = getter()
        assert client is mock_client

    def test_custom_attr(self):
        mod = MagicMock()
        mock_client = MagicMock()
        mod.CustomClient.return_value = mock_client
        getter = make_client_getter(
            module=mod,
            api_key_env="TEST_KEY",
            timeout_env="TEST_TIMEOUT",
            module_attr="CustomClient",
        )

        def _getenv(k, _d=None):
            return "key123" if k == "TEST_KEY" else None

        with patch("os.getenv", side_effect=_getenv):
            client = getter()
        assert client is mock_client

    def test_extra_kwargs(self):
        mod = MagicMock()
        mock_client = MagicMock()
        mod.OpenAI.return_value = mock_client
        getter = make_client_getter(
            module=mod,
            api_key_env="TEST_KEY",
            timeout_env="TEST_TIMEOUT",
            extra_client_kwargs={"org": "test"},
        )

        def _getenv(k, _d=None):
            return "key123" if k == "TEST_KEY" else None

        with patch("os.getenv", side_effect=_getenv):
            client = getter()
        assert client is mock_client

    def test_client_cls_none(self):
        mod = MagicMock()
        del mod.OpenAI
        getter = make_client_getter(
            module=mod,
            api_key_env="TEST_KEY",
            timeout_env="TEST_TIMEOUT",
        )

        def _getenv(k, _d=None):
            return "key123" if k == "TEST_KEY" else None

        with patch("os.getenv", side_effect=_getenv):
            client = getter()
        assert client is None

    def test_api_key_not_required(self):
        mod = MagicMock()
        mock_client = MagicMock()
        mod.OpenAI.return_value = mock_client
        getter = make_client_getter(
            module=mod,
            api_key_env="TEST_KEY",
            timeout_env="TEST_TIMEOUT",
            api_key_required=False,
        )
        with patch("os.getenv", return_value=None):
            client = getter()
        assert client is mock_client

    def test_api_key_in_extra_kwargs(self):
        mod = MagicMock()
        mock_client = MagicMock()
        mod.OpenAI.return_value = mock_client
        getter = make_client_getter(
            module=mod,
            api_key_env="TEST_KEY",
            timeout_env="TEST_TIMEOUT",
            extra_client_kwargs={"api_key": "preset"},
        )
        with patch("os.getenv", return_value=None):
            client = getter()
        assert client is mock_client


class TestMakeModelGetter:
    def test_default(self):
        getter = make_model_getter(prefix="test", default_model="m1")

        def _getenv(k, d=None):
            return d

        with patch("os.getenv", side_effect=_getenv):
            assert getter() == "m1"

    def test_env_override(self):
        getter = make_model_getter(prefix="test", default_model="m1")
        with patch("os.getenv", return_value="m2"):
            assert getter() == "m2"

    def test_ctx_override(self):
        getter = make_model_getter(prefix="test", default_model="m1")
        ctx = MagicMock()
        ctx.goal.metadata = {"test_model": "m3"}
        with patch("os.getenv", return_value=None):
            assert getter(ctx) == "m3"


class TestMakeTemperatureGetter:
    def test_default(self):
        getter = make_temperature_getter(prefix="test", default=0.5)
        assert getter() == 0.5

    def test_ctx_override(self):
        getter = make_temperature_getter(prefix="test", default=0.5)
        ctx = MagicMock()
        ctx.goal.metadata = {"test_temperature": 1.5}
        assert getter(ctx) == 1.5

    def test_clamp_high(self):
        getter = make_temperature_getter(
            prefix="test", default=0.5, temp_max=1.0
        )
        ctx = MagicMock()
        ctx.goal.metadata = {"test_temperature": 2.0}
        assert getter(ctx) == 1.0

    def test_clamp_low(self):
        getter = make_temperature_getter(
            prefix="test", default=0.5, temp_min=0.1
        )
        ctx = MagicMock()
        ctx.goal.metadata = {"test_temperature": -1.0}
        assert getter(ctx) == 0.1

    def test_invalid_value(self):
        getter = make_temperature_getter(prefix="test", default=0.5)
        ctx = MagicMock()
        ctx.goal.metadata = {"test_temperature": "bad"}
        assert getter(ctx) == 0.5


class TestMakeMaxTokensGetter:
    def test_default(self):
        getter = make_max_tokens_getter(prefix="test", default=500)
        assert getter() == 500

    def test_ctx_override(self):
        getter = make_max_tokens_getter(prefix="test", default=500)
        ctx = MagicMock()
        ctx.goal.metadata = {"test_max_tokens": 100}
        assert getter(ctx) == 100

    def test_clamp_high(self):
        getter = make_max_tokens_getter(
            prefix="test", default=500, token_max=1000
        )
        ctx = MagicMock()
        ctx.goal.metadata = {"test_max_tokens": 5000}
        assert getter(ctx) == 1000

    def test_invalid_value(self):
        getter = make_max_tokens_getter(prefix="test", default=500)
        ctx = MagicMock()
        ctx.goal.metadata = {"test_max_tokens": "bad"}
        assert getter(ctx) == 500


class TestChatSkill:
    def test_no_client(self):
        get_client = MagicMock(return_value=None)
        get_model = MagicMock(return_value="m1")
        get_temp = MagicMock(return_value=0.7)
        get_max = MagicMock(return_value=100)
        skill = _chat_skill("test", get_client, get_model, get_temp, get_max)
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "hi"
        mock_resp.choices[0].finish_reason = "stop"
        mock_resp.usage = None

        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        get_client = MagicMock(return_value=client)
        get_model = MagicMock(return_value="m1")
        get_temp = MagicMock(return_value=0.7)
        get_max = MagicMock(return_value=100)

        skill = _chat_skill("test", get_client, get_model, get_temp, get_max)
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "completed"
        assert result["message"] == "hi"

    def test_empty_choices(self):
        mock_resp = MagicMock()
        mock_resp.choices = []
        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        get_client = MagicMock(return_value=client)
        get_model = MagicMock(return_value="m1")
        get_temp = MagicMock(return_value=0.7)
        get_max = MagicMock(return_value=100)

        skill = _chat_skill("test", get_client, get_model, get_temp, get_max)
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "failed"

    def test_messages_from_metadata(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = "hi"
        mock_resp.choices[0].finish_reason = "stop"
        mock_resp.usage = None

        client = MagicMock()
        client.chat.completions.create.return_value = mock_resp
        get_client = MagicMock(return_value=client)
        get_model = MagicMock(return_value="m1")
        get_temp = MagicMock(return_value=0.7)
        get_max = MagicMock(return_value=100)

        skill = _chat_skill("test", get_client, get_model, get_temp, get_max)
        ctx = MagicMock()
        ctx.goal.metadata = {
            "messages": [{"role": "system", "content": "sys"}]
        }
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "completed"
        args = client.chat.completions.create.call_args
        assert args.kwargs["messages"] == [
            {"role": "system", "content": "sys"}
        ]


class TestCompletionSkill:
    def test_no_client(self):
        get_client = MagicMock(return_value=None)
        get_model = MagicMock(return_value="m1")
        get_temp = MagicMock(return_value=0.7)
        get_max = MagicMock(return_value=100)
        skill = _completion_skill(
            "test", get_client, get_model, get_temp, get_max
        )
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].text = "world"
        mock_resp.choices[0].finish_reason = "stop"
        mock_resp.usage = None

        client = MagicMock()
        client.completions.create.return_value = mock_resp
        get_client = MagicMock(return_value=client)
        get_model = MagicMock(return_value="m1")
        get_temp = MagicMock(return_value=0.7)
        get_max = MagicMock(return_value=100)

        skill = _completion_skill(
            "test", get_client, get_model, get_temp, get_max
        )
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "completed"
        assert result["text"] == "world"

    def test_empty_choices(self):
        mock_resp = MagicMock()
        mock_resp.choices = []
        client = MagicMock()
        client.completions.create.return_value = mock_resp
        get_client = MagicMock(return_value=client)
        get_model = MagicMock(return_value="m1")
        get_temp = MagicMock(return_value=0.7)
        get_max = MagicMock(return_value=100)

        skill = _completion_skill(
            "test", get_client, get_model, get_temp, get_max
        )
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "failed"


class TestEmbeddingSkill:
    def test_no_client(self):
        get_client = MagicMock(return_value=None)
        skill = _embedding_skill("test", get_client, "emb1")
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "failed"

    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.data = [MagicMock()]
        mock_resp.data[0].embedding = [0.1, 0.2]
        mock_resp.usage = None

        client = MagicMock()
        client.embeddings.create.return_value = mock_resp
        get_client = MagicMock(return_value=client)

        skill = _embedding_skill("test", get_client, "emb1")
        ctx = MagicMock()
        ctx.goal.metadata = {"text": "hello"}
        result = skill(ctx)
        assert result["status"] == "completed"
        assert result["embedding"] == [0.1, 0.2]

    def test_empty_data(self):
        mock_resp = MagicMock()
        mock_resp.data = []
        client = MagicMock()
        client.embeddings.create.return_value = mock_resp
        get_client = MagicMock(return_value=client)

        skill = _embedding_skill("test", get_client, "emb1")
        ctx = MagicMock()
        ctx.goal.metadata = {}
        ctx.goal.objective = "hello"
        result = skill(ctx)
        assert result["status"] == "failed"


class TestRegisterOpenaiProvider:
    def test_registers_skills(self):
        mod = MagicMock()
        with patch("uar.skills.llm_base.register_skill") as mock_reg:
            with patch("uar.skills.llm_base.skill_guard") as mock_guard:
                with patch(
                    "uar.skills.llm_base.with_circuit_breaker"
                ) as mock_cb:
                    mock_guard.return_value = lambda f: f
                    mock_cb.return_value = lambda f: f
                    register_openai_provider(
                        name="testprov",
                        module=mod,
                        api_key_env="TEST_KEY",
                        default_model="m1",
                    )
        assert mock_reg.call_count == 3
