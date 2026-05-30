"""Unit tests for uar.config coverage gaps."""

import os
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import patch

import pytest

from uar.config import (
    Config,
    validate_environment,
    validate_docker_environment,
)


class TestProductionSecretKey:
    def test_production_requires_secret_key(self):
        env = {"ENVIRONMENT": "production", "DEBUG": "false"}
        with mock.patch.dict(os.environ, env, clear=True):
            with pytest.raises(ValueError, match="SECRET_KEY"):
                Config()

    def test_production_accepts_secret_key(self):
        env = {
            "ENVIRONMENT": "production",
            "DEBUG": "false",
            "SECRET_KEY": "a-very-secret-key-1234567890",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config()
            assert cfg.secret_key == "a-very-secret-key-1234567890"

    def test_dev_generates_key_when_missing(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
            assert len(cfg.secret_key) > 0


class TestIsDefaultSecretKey:
    def test_none_is_default(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
            assert cfg._is_default_secret_key() is True

    def test_placeholder_values(self):
        placeholders = [
            "your-secret-key-here-must-be-changed-in-production",
            "change-me",
            "changeme",
            "secret",
        ]
        for val in placeholders:
            with mock.patch.dict(
                os.environ, {"SECRET_KEY": val}, clear=True
            ):
                cfg = Config()
                assert cfg._is_default_secret_key() is True

    def test_real_key_is_not_default(self):
        with mock.patch.dict(
            os.environ, {"SECRET_KEY": "real-key-123"}, clear=True
        ):
            cfg = Config()
            assert cfg._is_default_secret_key() is False


class TestDatabaseUrl:
    def test_returns_url(self):
        env = {"DATABASE_URL": "postgres://localhost/uar"}
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config()
            assert cfg.database_url == "postgres://localhost/uar"

    def test_returns_none(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
            assert cfg.database_url is None


class TestValidate:
    def test_valid_config(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
            assert cfg.validate() == []

    def test_invalid_port(self):
        with mock.patch.dict(os.environ, {"API_PORT": "0"}, clear=True):
            with pytest.raises(ValueError, match="API_PORT"):
                Config()

    def test_negative_rate_limit(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
            cfg.rate_limit_anonymous = -1
            issues = cfg.validate()
            assert any("Rate limits" in i for i in issues)

    def test_zero_max_file_size(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
            cfg.max_file_size = 0
            issues = cfg.validate()
            assert any("Max file size" in i for i in issues)

    def test_production_with_default_secret(self):
        env = {
            "ENVIRONMENT": "production",
            "DEBUG": "false",
            "SECRET_KEY": "secret",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config()
            issues = cfg.validate()
            assert any("Production deployment" in i for i in issues)


class TestSetupLogging:
    def test_development_logging(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = Config()
            cfg.setup_logging()

    def test_production_logging_writable(self, tmp_path):
        env = {
            "ENVIRONMENT": "production",
            "DEBUG": "false",
            "SECRET_KEY": "real-key-123",
            "LOG_FILE_PATH": str(tmp_path / "app.log"),
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config()
            cfg.setup_logging()

    def test_production_logging_unwritable(self):
        env = {
            "ENVIRONMENT": "production",
            "DEBUG": "false",
            "SECRET_KEY": "real-key-123",
            "LOG_FILE_PATH": "/nonexistent/path/app.log",
        }
        with mock.patch.dict(os.environ, env, clear=True):
            cfg = Config()
            with patch("sys.stderr.write") as mock_write:
                cfg.setup_logging()
            mock_write.assert_called_once()


class TestValidateEnvironment:
    def test_python_version(self):
        from collections import namedtuple
        VInfo = namedtuple("VInfo", ["major", "minor"])
        with mock.patch.object(sys, "version_info", VInfo(3, 9)):
            issues = validate_environment()
            assert any("Python" in i for i in issues)

    def test_writable_directory_error(self):
        with mock.patch.object(
            Path, "mkdir", side_effect=PermissionError("denied")
        ):
            issues = validate_environment()
            assert any("Cannot write" in i for i in issues)


class TestValidateDockerEnvironment:
    def test_not_in_docker(self):
        with mock.patch("os.path.exists", return_value=False):
            with mock.patch.dict(os.environ, {}, clear=True):
                issues = validate_docker_environment()
                assert issues == []

    def test_docker_root(self):
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch.dict(
                os.environ, {"DOCKER_CONTAINER": "true"}, clear=True
            ):
                with mock.patch.object(os, "getuid", return_value=0):
                    issues = validate_docker_environment()
                    assert any("root" in i for i in issues)

    def test_docker_missing_env(self):
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch.dict(
                os.environ, {"DOCKER_CONTAINER": "true"}, clear=True
            ):
                with mock.patch.object(os, "getuid", return_value=1000):
                    issues = validate_docker_environment()
                    assert any("ENVIRONMENT" in i for i in issues)

    def test_docker_no_getuid(self):
        original_hasattr = hasattr

        def fake_hasattr(obj, name):
            if obj is os and name == "getuid":
                return False
            return original_hasattr(obj, name)
        with mock.patch("os.path.exists", return_value=True):
            with mock.patch.dict(
                os.environ,
                {"DOCKER_CONTAINER": "true", "ENVIRONMENT": "production"},
                clear=True,
            ):
                with mock.patch("builtins.hasattr", fake_hasattr):
                    issues = validate_docker_environment()
                    assert issues == []
