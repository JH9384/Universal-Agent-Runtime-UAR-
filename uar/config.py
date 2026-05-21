"""Production configuration management for UAR"""

import os
import secrets
import sys
from pathlib import Path
from typing import Optional
import logging
import logging.config

# Constants
DEFAULT_API_PORT = 8000
DEFAULT_API_WORKERS = 1
DEFAULT_RATE_LIMIT_ANONYMOUS = 10
DEFAULT_RATE_LIMIT_AUTHENTICATED = 100
DEFAULT_RATE_LIMIT_WINDOW = 60  # seconds
DEFAULT_MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
DEFAULT_MAX_FILES = 1000
DEFAULT_OLLAMA_TIMEOUT = 60  # seconds
DEFAULT_AUTONOMI_TIMEOUT = 300  # seconds (5 minutes)
DEFAULT_METRICS_PORT = 9090
SECRET_KEY_LENGTH = 32
MAX_PORT_NUMBER = 65535
MIN_PYTHON_MAJOR = 3
MIN_PYTHON_MINOR = 10


class Config:
    """Centralized configuration management"""

    def __init__(self):
        self.load_from_env()

    def load_from_env(self):
        """Load configuration from environment variables"""
        # API Configuration
        self.api_host = os.getenv("API_HOST", "127.0.0.1")
        self.api_port = int(os.getenv("API_PORT", str(DEFAULT_API_PORT)))
        self.api_workers = int(
            os.getenv("API_WORKERS", str(DEFAULT_API_WORKERS))
        )

        # Debug flag must be set before is_production check
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "info").upper()

        # Security Configuration
        # In production, SECRET_KEY must be explicitly set
        # In development, generate one if not set
        if self.is_production:
            secret_key = os.getenv("SECRET_KEY")
            if not secret_key:
                raise ValueError(
                    "SECRET_KEY environment variable must be set in production"
                )
            self.secret_key = secret_key
        else:
            self.secret_key = os.getenv(
                "SECRET_KEY", self._generate_secret_key()
            )

        # Rate Limiting
        self.rate_limit_enabled = (
            os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        )
        self.rate_limit_anonymous = int(
            os.getenv(
                "RATE_LIMIT_ANONYMOUS", str(DEFAULT_RATE_LIMIT_ANONYMOUS)
            )
        )
        self.rate_limit_authenticated = int(
            os.getenv(
                "RATE_LIMIT_AUTHENTICATED",
                str(DEFAULT_RATE_LIMIT_AUTHENTICATED),
            )
        )
        self.rate_limit_window = int(
            os.getenv("RATE_LIMIT_WINDOW", str(DEFAULT_RATE_LIMIT_WINDOW))
        )

        # File Storage
        self.runs_dir = Path(os.getenv("RUNS_DIR", "runs"))
        self.max_file_size = int(
            os.getenv("MAX_FILE_SIZE", str(DEFAULT_MAX_FILE_SIZE))
        )  # 10MB
        self.max_files = int(os.getenv("MAX_FILES", str(DEFAULT_MAX_FILES)))

        # Ollama Configuration
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.ollama_timeout = int(
            os.getenv("OLLAMA_TIMEOUT_SECONDS", str(DEFAULT_OLLAMA_TIMEOUT))
        )

        # Production Settings
        cors_origins_str = os.getenv(
            "CORS_ORIGINS", "http://localhost:3000,http://localhost:5173"
        )
        self.cors_origins = [
            origin.strip()
            for origin in cors_origins_str.split(",")
            if origin.strip()
        ]
        self.max_request_size = int(
            os.getenv("MAX_REQUEST_SIZE", str(DEFAULT_MAX_FILE_SIZE))
        )  # 10MB
        self.max_request_body_bytes = int(
            os.getenv("MAX_REQUEST_BODY_BYTES", str(DEFAULT_MAX_FILE_SIZE))
        )  # 10MB

        # Library and storage paths
        project_root = Path(__file__).parent.parent.parent
        self.uar_library_dir = Path(
            os.getenv("UAR_LIBRARY_DIR", project_root / ".uar_library")
        )
        self.uar_graphrag_root = Path(
            os.getenv("UAR_GRAPHRAG_ROOT", project_root / ".uar_graphrag")
        )

        # UOR object/runtime store (consolidated from apps/api-python).
        # Path priority: UOR_DB_PATH (preferred) > legacy DB_PATH >
        # default ./uar.sqlite3 next to the runtime working directory.
        self.uor_db_path = Path(
            os.getenv("UOR_DB_PATH") or os.getenv("DB_PATH") or "uar.sqlite3"
        )

        # Optional UOR extensions (atlas, prism, sigmatics, ego-guard).
        # Off by default so missing optional deps never break the
        # default-import path; opt in via env.
        self.uor_extensions_enabled = (
            os.getenv("UAR_ENABLE_UOR_EXTENSIONS", "false").lower() == "true"
        )

        # Autonomi Network Configuration
        self.autonomi_private_key = os.getenv("AUTONOMI_PRIVATE_KEY")
        self.autonomi_network = os.getenv("AUTONOMI_NETWORK", "testnet")
        self.autonomi_timeout_sec = int(
            os.getenv("AUTONOMI_TIMEOUT_SEC", str(DEFAULT_AUTONOMI_TIMEOUT))
        )

        # Metrics Configuration
        # Support both new METRICS_ENABLED and legacy ENABLE_METRICS
        # for backward compatibility. Use explicit None check to allow
        # explicit empty string to disable metrics.
        metrics_env = os.getenv("METRICS_ENABLED")
        if metrics_env is None:
            metrics_env = os.getenv("ENABLE_METRICS", "true")
        self.metrics_enabled = metrics_env.lower() == "true"
        self.metrics_port = int(
            os.getenv("METRICS_PORT", str(DEFAULT_METRICS_PORT))
        )

    def _generate_secret_key(self) -> str:
        """Generate a secret key for development -
        always generates a new key."""
        return secrets.token_urlsafe(SECRET_KEY_LENGTH)

    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return not self.debug and os.getenv("ENVIRONMENT") == "production"

    # Known placeholder values shipped in templates / docs that must never
    # be accepted in production.
    _PLACEHOLDER_SECRETS = {
        "your-secret-key-here-must-be-changed-in-production",
        "change-me",
        "changeme",
        "secret",
    }

    def _is_default_secret_key(self) -> bool:
        """Return True if SECRET_KEY is unset or a known placeholder."""
        raw = os.getenv("SECRET_KEY")
        if raw is None:
            return True
        return raw.strip().lower() in self._PLACEHOLDER_SECRETS

    @property
    def database_url(self) -> Optional[str]:
        """Get database URL (future use)"""
        return os.getenv("DATABASE_URL")

    def validate(self) -> list[str]:
        """Validate configuration and return any issues"""
        issues = []

        if self.api_port < 1 or self.api_port > MAX_PORT_NUMBER:
            issues.append(f"Invalid API port: {self.api_port}")

        if (
            self.rate_limit_anonymous <= 0
            or self.rate_limit_authenticated <= 0
        ):
            issues.append("Rate limits must be positive numbers")

        if self.max_file_size <= 0:
            issues.append("Max file size must be positive")

        # Check for production secret key requirement
        if self.is_production and self._is_default_secret_key():
            issues.append(
                "Production deployment requires an explicitly set "
                "SECRET_KEY environment variable"
            )

        return issues

    def setup_logging(self):
        """Setup logging configuration"""
        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",  # noqa
                },
                "json": {
                    "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '  # noqa
                    '"logger": "%(name)s", "message": "%(message)s"}',
                },
            },
            "handlers": {
                "console": {
                    "class": "logging.StreamHandler",
                    "formatter": "json" if self.is_production else "default",
                    "level": self.log_level,
                },
            },
            "root": {
                "level": self.log_level,
                "handlers": ["console"],
            },
        }

        # Add file logging in production (if path is writable)
        if self.is_production:
            log_file_path = os.getenv("LOG_FILE_PATH", "/var/log/uar/app.log")
            try:
                # Ensure log directory exists
                log_dir = Path(log_file_path).parent
                log_dir.mkdir(parents=True, exist_ok=True)
                # Test writability
                test_file = log_dir / ".write_test"
                test_file.write_text("test")
                test_file.unlink()

                log_config["handlers"]["file"] = {
                    "class": "logging.FileHandler",
                    "filename": log_file_path,
                    "formatter": "json",
                    "level": self.log_level,
                }
                log_config["root"]["handlers"].append("file")
            except (OSError, PermissionError):
                # Log directory not writable, use stdout only
                import sys

                sys.stderr.write(
                    f"Warning: Log directory not writable: {log_dir}. "
                    "Using stdout only.\n"
                )

        logging.config.dictConfig(log_config)


def validate_environment() -> list[str]:
    """Validate the runtime environment before starting.

    Returns a list of issues. Empty list means environment is valid.
    """
    issues = []

    # Check Python version
    if sys.version_info < (MIN_PYTHON_MAJOR, MIN_PYTHON_MINOR):
        issues.append(
            f"Python {MIN_PYTHON_MAJOR}.{MIN_PYTHON_MINOR}+ required, "
            f"found {sys.version_info.major}.{sys.version_info.minor}"
        )

    # Check required directories are writable
    test_dirs = [
        config.runs_dir,
        Path("/var/lib/uar")
        if os.path.exists("/var/lib/uar")
        else config.runs_dir,
    ]

    for test_dir in test_dirs:
        try:
            test_dir.mkdir(parents=True, exist_ok=True)
            # Try to create a test file
            test_file = test_dir / ".write_test"
            test_file.write_text("test")
            test_file.unlink()
        except (OSError, PermissionError) as e:
            issues.append(f"Cannot write to directory {test_dir}: {e}")

    # Validate configuration
    config_issues = config.validate()
    issues.extend(config_issues)

    return issues


def validate_docker_environment() -> list[str]:
    """Validate Docker environment specifically.

    Called by entrypoint scripts to ensure container is properly configured.
    """
    issues = []

    # Check if running in Docker
    in_docker = os.path.exists("/.dockerenv") or os.getenv(
        "DOCKER_CONTAINER", False
    )

    if in_docker:
        # In Docker, certain things should always be true
        # os.getuid() is Unix-only; skip root check on Windows
        if hasattr(os, "getuid") and os.getuid() == 0:
            issues.append(
                "Running as root in Docker container "
                "(should use non-root user)"
            )

        # Check required environment variables in Docker
        required_env = ["ENVIRONMENT"]
        for env_var in required_env:
            if not os.getenv(env_var):
                issues.append(
                    f"Required environment variable {env_var} "
                    f"not set in Docker"
                )

    return issues


# Global config instance
config = Config()
