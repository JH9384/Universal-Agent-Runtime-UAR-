"""Tests for version helpers.

Covers get_uar_version and get_uor_version.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

from uar.version import get_uar_version
from uar.compat.uor_version import get_uor_version


class TestGetUarVersion:
    """UAR package version."""

    def test_reads_version_file(self):
        # The actual VERSION file should exist in the repo
        version = get_uar_version()
        assert version != "unknown"
        assert isinstance(version, str)

    def test_missing_file(self):
        missing_path = Path("/nonexistent/VERSION")
        with patch("uar.version.VERSION_FILE", missing_path):
            get_uar_version.cache_clear()
            version = get_uar_version()
            assert version == "unknown"
            get_uar_version.cache_clear()

    def test_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "VERSION"
            path.write_text("   \n")
            with patch("uar.version.VERSION_FILE", path):
                get_uar_version.cache_clear()
                version = get_uar_version()
                assert version == "unknown"
                get_uar_version.cache_clear()


class TestGetUorVersion:
    """UOR framework version."""

    def test_missing_file(self):
        missing_path = Path("/nonexistent/VERSION")
        with patch("uar.compat.uor_version.UOR_VERSION_FILE", missing_path):
            get_uor_version.cache_clear()
            version = get_uor_version()
            assert version == "unknown"
            get_uor_version.cache_clear()

    def test_reads_version_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "VERSION"
            path.write_text("v0.1.0")
            with patch("uar.compat.uor_version.UOR_VERSION_FILE", path):
                get_uor_version.cache_clear()
                version = get_uor_version()
                assert version == "v0.1.0"
                get_uor_version.cache_clear()
