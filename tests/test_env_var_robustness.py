"""Regression tests for env-var parsing crashes across the codebase.

Prior to these fixes, setting any of the following env vars to a
non-numeric value (e.g. ``"bad"``) would raise ``ValueError`` at
*import time*, making the entire module (and anything that imported
it) unusable.
"""

from unittest.mock import patch


class TestMathComputeEnvVars:
    def test_math_timeout_invalid(self):
        with patch.dict("os.environ", {"MATH_TIMEOUT_SECONDS": "bad"}):
            from uar.skills.math_compute import _get_math_timeout
            assert _get_math_timeout() == 30.0

    def test_math_max_expression_size_invalid(self):
        with patch.dict(
            "os.environ", {"MATH_MAX_EXPRESSION_SIZE": "bad"}
        ):
            from uar.skills.math_compute import _get_max_expression_size
            assert _get_max_expression_size() == 10000


class TestPhysicsComputeEnvVars:
    def test_physics_timeout_invalid(self):
        with patch.dict(
            "os.environ", {"PHYSICS_TIMEOUT_SECONDS": "bad"}
        ):
            from uar.skills.physics_compute import _get_physics_timeout
            assert _get_physics_timeout() == 30.0

    def test_physics_max_data_size_invalid(self):
        with patch.dict(
            "os.environ", {"PHYSICS_MAX_DATA_SIZE": "bad"}
        ):
            from uar.skills.physics_compute import _get_max_data_size
            assert _get_max_data_size() == 10485760


class TestDistributedEnvVars:
    def test_pool_size_invalid(self):
        with patch.dict(
            "os.environ", {"UAR_DISTRIBUTED_POOL_SIZE": "bad"}
        ):
            from uar.core.distributed import _get_default_pool_size
            assert _get_default_pool_size() == 4

    def test_timeout_invalid(self):
        with patch.dict(
            "os.environ", {"UAR_DISTRIBUTED_TIMEOUT": "bad"}
        ):
            from uar.core.distributed import _get_default_timeout
            assert _get_default_timeout() == 30.0


class TestBootEnvVar:
    def test_shutdown_sleep_invalid(self):
        with patch.dict(
            "os.environ", {"SHUTDOWN_GRACE_SECONDS": "bad"}
        ):
            from uar.boot import _get_shutdown_sleep
            assert _get_shutdown_sleep() == 30.0


class TestHttpClientEnvVars:
    def test_max_retries_invalid(self):
        with patch.dict(
            "os.environ", {"UAR_HTTP_MAX_RETRIES": "bad"}
        ):
            from uar.core.http_client import _get_int_env
            assert _get_int_env("UAR_HTTP_MAX_RETRIES", 3, 0, 10) == 3

    def test_base_delay_invalid(self):
        with patch.dict(
            "os.environ", {"UAR_HTTP_BASE_DELAY": "bad"}
        ):
            from uar.core.http_client import _get_float_env
            assert _get_float_env("UAR_HTTP_BASE_DELAY", 0.5, 0.0, 5.0) == 0.5


class TestAlmTimeoutEnvVar:
    def test_alm_timeout_invalid(self):
        with patch.dict("os.environ", {"ALM_TIMEOUT_SEC": "bad"}):
            from uar.skills.atomic_lang_model import _get_http_client
            from unittest.mock import MagicMock, patch as _patch
            with _patch(
                "uar.skills.atomic_lang_model.HTTPX_AVAILABLE", True
            ):
                with _patch(
                    "uar.skills.atomic_lang_model.httpx"
                ) as mock_httpx:
                    with _patch(
                        "uar.skills.atomic_lang_model._http_client", None
                    ):
                        mock_client = MagicMock()
                        mock_httpx.Client.return_value = mock_client
                        client = _get_http_client()
                        assert client is mock_client
                        kwargs = mock_httpx.Client.call_args.kwargs
                        assert kwargs["timeout"] == 30.0
