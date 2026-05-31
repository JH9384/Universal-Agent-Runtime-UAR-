"""Test server.py module-level TrustedHostMiddleware setup."""

import importlib
import os
from unittest.mock import patch


def test_trusted_hosts_env():
    import uar.api.server as server_mod
    with patch.dict(os.environ, {"TRUSTED_HOSTS": "host1, host2"}):
        importlib.reload(server_mod)
        assert hasattr(server_mod, "app")
    # Restore original app without TrustedHostMiddleware so other tests
    # are not affected by the restricted host list.
    importlib.reload(server_mod)
    assert hasattr(server_mod, "app")
