"""
Security utilities for UAR API.
"""

import os
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class SecurityManager:
    """Manages API keys and security policies."""

    def __init__(self):
        # Import from middleware to use single source of truth
        from .middleware import API_KEYS

        self.api_keys = API_KEYS

    def validate_api_key(self, key: str) -> Optional[Dict[str, str]]:
        """Validate an API key and return user info."""
        if key in self.api_keys:
            return self.api_keys[key]
        return None

    def is_production(self) -> bool:
        """Check if running in production mode."""
        return os.getenv("ENVIRONMENT", "development").lower() == "production"


# Global security manager instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance."""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager
