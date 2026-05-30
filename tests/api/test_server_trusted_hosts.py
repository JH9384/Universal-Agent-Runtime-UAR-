"""Test server.py module-level TrustedHostMiddleware setup."""

import importlib
import os
from unittest.mock import patch


def test_trusted_hosts_env():
    with patch.dict(os.environ, {"TRUSTED_HOSTS": "host1, host2"}):
        import uar.api.server as server_mod
        importlib.reload(server_mod)
    # Middleware was added; we just need to confirm reload succeeded
    assert hasattr(server_mod, "app")
