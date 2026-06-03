"""Tests for validate_path_security and _has_symlink_in_path.

These cover the symlink-detection fix for KNOWN_BUG_TEST_LIST F2.
"""

import os

import pytest

from uar.core.exceptions import PathSecurityError
from uar.core.validation import _has_symlink_in_path, validate_path_security


class TestHasSymlinkInPath:
    """Unit tests for the _has_symlink_in_path helper."""

    def test_no_symlink_returns_false(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        doc = safe / "doc.txt"
        doc.write_text("hello")
        assert _has_symlink_in_path(doc, safe) is False

    def test_intermediate_symlink_detected(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        sub = safe / "subdir"
        sub.mkdir()
        link = safe / "link"
        link.symlink_to(sub)
        assert _has_symlink_in_path(link / "doc.txt", safe) is True

    def test_final_component_symlink_detected(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        real = safe / "real.txt"
        real.write_text("x")
        link = safe / "link.txt"
        link.symlink_to(real)
        assert _has_symlink_in_path(link, safe) is True

    def test_broken_symlink_detected(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        broken = safe / "broken"
        broken.symlink_to("/does/not/exist")
        assert _has_symlink_in_path(broken, safe) is True

    def test_symlink_chain_detected(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        a = safe / "a"
        a.mkdir()
        link1 = safe / "link1"
        link1.symlink_to(a)
        link2 = safe / "link2"
        link2.symlink_to(link1)
        assert _has_symlink_in_path(link2, safe) is True


class TestValidatePathSecuritySymlinkFix:
    """Integration tests for the fixed validate_path_security behaviour."""

    def test_intermediate_symlink_inside_root_raises(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        sub = safe / "subdir"
        sub.mkdir()
        link = safe / "link"
        link.symlink_to(sub)

        with pytest.raises(PathSecurityError) as exc_info:
            validate_path_security(link / "doc.txt", safe)
        assert "Symlinks" in exc_info.value.reason

    def test_resolved_path_outside_root_raises(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        secret = tmp_path / "secret.txt"
        secret.write_text("secret")
        link = safe / "link.txt"
        link.symlink_to(secret)

        with pytest.raises(PathSecurityError) as exc_info:
            validate_path_security(link, safe)
        assert "outside" in exc_info.value.reason

    def test_broken_symlink_raises(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        broken = safe / "broken"
        broken.symlink_to("/nowhere")

        with pytest.raises(PathSecurityError) as exc_info:
            validate_path_security(broken, safe)
        # Broken symlinks are caught by either the resolved-path check
        # (target outside root) or the _has_symlink_in_path check.
        assert (
            "Symlinks" in exc_info.value.reason
            or "outside" in exc_info.value.reason
        )

    def test_normal_file_passes(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()
        doc = safe / "doc.txt"
        doc.write_text("hello")
        # Should not raise
        validate_path_security(doc, safe)

    def test_traversal_via_dotdot_blocked(self, tmp_path):
        safe = tmp_path / "safe"
        safe.mkdir()

        with pytest.raises(PathSecurityError):
            validate_path_security(safe / ".." / "secret", safe)

    def test_nofollow_open_rejects_symlink(self, tmp_path):
        """Direct O_NOFOLLOW test: opening a symlink path must fail."""
        safe = tmp_path / "safe"
        safe.mkdir()
        real = safe / "real.txt"
        real.write_text("data")
        link = safe / "link.txt"
        link.symlink_to(real)

        if hasattr(os, "O_NOFOLLOW"):
            with pytest.raises(OSError):
                fd = os.open(link, os.O_RDONLY | os.O_NOFOLLOW)
                os.close(fd)

    def test_source_no_resolved_path_symlink_loop(self):
        """Source inspection: the old resolved-path symlink loop must be
        gone so it cannot silently miss intermediate symlinks."""
        import inspect

        src = inspect.getsource(validate_path_security)
        assert "resolved_path.parts" not in src
        assert "for part in" not in src or "_has_symlink_in_path" in src
