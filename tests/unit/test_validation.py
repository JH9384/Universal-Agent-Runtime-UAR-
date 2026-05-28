"""Unit tests for validation module"""

import pytest
from pathlib import Path

from uar.core.validation import (
    validate_goal,
    validate_skills,
    validate_input_path,
    validate_path_security,
    ValidationError,
)


class TestValidateGoal:
    """Test goal validation"""

    def test_valid_goal(self):
        """Valid goal passes validation"""
        result = validate_goal("Explain gravity simply")
        assert result == "Explain gravity simply"

    def test_empty_goal(self):
        """Empty goal is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_goal("")
        assert "cannot be empty" in str(exc_info.value)
        assert exc_info.value.field == "goal"

    def test_whitespace_only_goal(self):
        """Whitespace-only goal is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_goal("   ")
        assert "cannot be empty" in str(exc_info.value)

    def test_goal_too_short(self):
        """Goal shorter than minimum is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_goal("hi")
        assert "at least 3 characters" in str(exc_info.value)

    def test_goal_too_long(self):
        """Goal exceeding maximum length is rejected"""
        long_goal = "x" * 10001
        with pytest.raises(ValidationError) as exc_info:
            validate_goal(long_goal)
        assert "cannot exceed 10,000 characters" in str(exc_info.value)

    def test_dangerous_content_script(self):
        """Script tags are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_goal("<script>alert('xss')</script>")
        assert "dangerous content" in str(exc_info.value)

    def test_dangerous_content_javascript(self):
        """JavaScript URLs are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_goal("javascript:alert('xss')")
        assert "dangerous content" in str(exc_info.value)

    def test_dangerous_content_data_url(self):
        """Data URLs are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_goal("data:text/html,<script>alert('xss')</script>")
        assert "dangerous content" in str(exc_info.value)


class TestValidateSkills:
    """Test skills validation"""

    def test_valid_skills(self):
        """Valid skills list passes validation"""
        result = validate_skills(["section_sum", "doc_ingest"])
        assert result == ["section_sum", "doc_ingest"]

    def test_none_skills(self):
        """None skills returns empty list"""
        result = validate_skills(None)
        assert result == []

    def test_empty_skills(self):
        """Empty skills list returns empty list"""
        result = validate_skills([])
        assert result == []

    def test_too_many_skills(self):
        """Too many skills is rejected"""
        skills = [f"skill_{i}" for i in range(25)]
        with pytest.raises(ValidationError) as exc_info:
            validate_skills(skills)
        assert "more than 20 skills" in str(exc_info.value)

    def test_invalid_characters_spaces(self):
        """Skills with spaces are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_skills(["skill with spaces"])
        assert "invalid characters" in str(exc_info.value)

    def test_invalid_characters_special(self):
        """Skills with special characters are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_skills(["skill@invalid"])
        assert "invalid characters" in str(exc_info.value)

    def test_invalid_characters_slash(self):
        """Skills with slashes are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_skills(["skill/invalid"])
        assert "invalid characters" in str(exc_info.value)

    def test_skill_name_too_long(self):
        """Skill name exceeding maximum length is rejected"""
        long_skill = ["a" * 101]
        with pytest.raises(ValidationError) as exc_info:
            validate_skills(long_skill)
        assert "cannot exceed 100 characters" in str(exc_info.value)


class TestValidateInputPath:
    """Test input path validation"""

    def test_valid_relative_path(self):
        """Valid relative path passes validation"""
        result = validate_input_path("./docs")
        assert result == "./docs"

    def test_path_traversal_parent(self):
        """Path traversal with parent directory is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_input_path("../../../etc/passwd")
        assert "Path traversal" in str(exc_info.value)

    def test_path_traversal_backslash(self):
        """Path traversal with backslashes is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_input_path("..\\..\\windows\\system32")
        assert "Path traversal" in str(exc_info.value)

    def test_absolute_path(self):
        """Absolute path is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_input_path("/etc/passwd")
        assert "Absolute paths" in str(exc_info.value)

    def test_null_bytes(self):
        """Paths with null bytes are rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_input_path("test\x00file")
        assert "null bytes" in str(exc_info.value)

    def test_hex_encoded_traversal(self):
        """Hex-encoded path traversal is rejected"""
        with pytest.raises(ValidationError) as exc_info:
            validate_input_path("%2e%2e%2fetc/passwd")
        assert "Path traversal" in str(exc_info.value)


class TestValidatePathSecurity:
    """Test path security validation"""

    def test_path_within_allowed_root(self):
        """Path within allowed root is accepted"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed_root = Path(tmpdir)
            test_file = allowed_root / "test.txt"
            test_file.write_text("test content")

            try:
                validate_path_security(test_file, allowed_root)
            finally:
                test_file.unlink()

    def test_path_outside_allowed_root(self):
        """Path outside allowed root is rejected"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed_root = Path(tmpdir)
            outside_path = Path(tmpdir).parent / "outside.txt"

            with pytest.raises(Exception) as exc_info:
                validate_path_security(outside_path, allowed_root)
            assert "Path security violation" in str(exc_info.value)

    def test_symlink_rejection(self):
        """Symlinks are rejected"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed_root = Path(tmpdir)
            target_file = allowed_root / "target.txt"
            target_file.write_text("target content")

            symlink_path = allowed_root / "symlink.txt"
            symlink_path.symlink_to(target_file)

            try:
                with pytest.raises(Exception) as exc_info:
                    validate_path_security(symlink_path, allowed_root)
                assert "Path security violation" in str(exc_info.value)
            finally:
                target_file.unlink()
                symlink_path.unlink()

    def test_nonexistent_path_within_root(self):
        """Nonexistent path within root is accepted"""
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            allowed_root = Path(tmpdir)
            nonexistent = allowed_root / "nonexistent.txt"

            # Should not raise exception for nonexistent path
            validate_path_security(nonexistent, allowed_root)
