"""
Security utilities for UAR API.
"""
import os
import logging

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages security configuration and validation."""

    def __init__(self):
        self.secret_key = os.getenv("SECRET_KEY")
        self.api_keys = self._load_api_keys()

    def _load_api_keys(self) -> dict:
        """Load API keys from environment variable."""
        api_keys_str = os.getenv("API_KEYS", "")
        keys = {}
        if api_keys_str:
            for key_part in api_keys_str.split(","):
                parts = key_part.split(":")
                if len(parts) >= 2:
                    key_id = parts[0]
                    user = parts[1]
                    tier = parts[2] if len(parts) > 2 else "default"
                    keys[key_id] = {"user": user, "tier": tier}
        return keys

    def validate_api_key(self, key: str) -> dict:
        """Validate an API key and return user info."""
        if key in self.api_keys:
            return self.api_keys[key]
        return None

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"


# Global security manager instance
_security_manager = None


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager
