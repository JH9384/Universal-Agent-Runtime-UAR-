"""Production configuration management for UAR"""

import os
from typing import Optional
from pathlib import Path
import logging


class Config:
    """Centralized configuration management"""
    
    def __init__(self):
        self.load_from_env()
    
    def load_from_env(self):
        """Load configuration from environment variables"""
        # API Configuration
        self.api_host = os.getenv("API_HOST", "127.0.0.1")
        self.api_port = int(os.getenv("API_PORT", "8000"))
        self.api_workers = int(os.getenv("API_WORKERS", "1"))
        
        # Security Configuration
        self.secret_key = os.getenv("SECRET_KEY", self._generate_secret_key())
        self.debug = os.getenv("DEBUG", "false").lower() == "true"
        self.log_level = os.getenv("LOG_LEVEL", "info").upper()
        
        # Rate Limiting
        self.rate_limit_enabled = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
        self.rate_limit_anonymous = int(os.getenv("RATE_LIMIT_ANONYMOUS", "10"))
        self.rate_limit_authenticated = int(os.getenv("RATE_LIMIT_AUTHENTICATED", "100"))
        self.rate_limit_window = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
        
        # File Storage
        self.runs_dir = Path(os.getenv("RUNS_DIR", "runs"))
        self.max_file_size = int(os.getenv("MAX_FILE_SIZE", str(10 * 1024 * 1024)))  # 10MB
        self.max_files = int(os.getenv("MAX_FILES", "1000"))
        
        # Ollama Configuration
        self.ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.ollama_timeout = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
        
        # Production Settings
        self.cors_origins = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")
        self.max_request_size = int(os.getenv("MAX_REQUEST_SIZE", str(10 * 1024 * 1024)))  # 10MB
        
        # Monitoring
        self.enable_metrics = os.getenv("ENABLE_METRICS", "false").lower() == "true"
        self.metrics_port = int(os.getenv("METRICS_PORT", "9090"))
    
    def _generate_secret_key(self) -> str:
        """Generate a secret key for development"""
        import secrets
        return secrets.token_urlsafe(32)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode"""
        return not self.debug and os.getenv("ENVIRONMENT") == "production"
    
    @property
    def database_url(self) -> Optional[str]:
        """Get database URL (future use)"""
        return os.getenv("DATABASE_URL")
    
    def validate(self) -> list[str]:
        """Validate configuration and return any issues"""
        issues = []
        
        if self.api_port < 1 or self.api_port > 65535:
            issues.append(f"Invalid API port: {self.api_port}")
        
        if self.rate_limit_anonymous <= 0 or self.rate_limit_authenticated <= 0:
            issues.append("Rate limits must be positive numbers")
        
        if self.max_file_size <= 0:
            issues.append("Max file size must be positive")
        
        if self.is_production and self.secret_key == self._generate_secret_key():
            issues.append("Production deployment requires a custom SECRET_KEY")
        
        return issues
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_config = {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
                "json": {
                    "format": '{"timestamp": "%(asctime)s", "level": "%(levelname)s", "logger": "%(name)s", "message": "%(message)s"}',
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
        
        # Add file logging in production
        if self.is_production:
            log_config["handlers"]["file"] = {
                "class": "logging.FileHandler",
                "filename": "/var/log/uar/app.log",
                "formatter": "json",
                "level": self.log_level,
            }
            log_config["root"]["handlers"].append("file")
        
        logging.config.dictConfig(log_config)


# Global config instance
config = Config()
