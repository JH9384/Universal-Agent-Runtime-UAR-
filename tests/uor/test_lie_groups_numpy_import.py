"""Test lie_groups module import without numpy."""

import importlib
import sys
from unittest.mock import patch


def test_numpy_import_error():
    """Reload module with numpy unavailable to cover lines 17-19."""
    import uar.uor.lie_groups as lg_mod

    # Remove numpy from sys.modules temporarily
    removed = {}
    for key in list(sys.modules.keys()):
        if key == "numpy" or key.startswith("numpy."):
            removed[key] = sys.modules.pop(key)

    try:
        with patch.dict(sys.modules, {"numpy": None}, clear=False):
            importlib.reload(lg_mod)
        assert lg_mod.NUMPY_AVAILABLE is False
    finally:
        # Restore removed modules
        sys.modules.update(removed)
        importlib.reload(lg_mod)
        assert lg_mod.NUMPY_AVAILABLE is True
