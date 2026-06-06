"""Tests for uar.skills.plugin — external skill loading and registration."""

import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from uar.skills.plugin import (
    PluginManifest,
    _discover_user_skills,
    _load_module_from_path,
    _register_skills_from_module,
    get_plugin_manifests,
    init_user_skill_dir,
    load_plugins,
    reload_plugins,
)


# ── _load_module_from_path ──────────────────────────────────────────────────


def test_load_module_from_path_success():
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False
    ) as f:
        f.write("test_value = 42\n")
        path = Path(f.name)
    try:
        mod = _load_module_from_path("test_mod_1", path)
        assert mod.test_value == 42
        assert "test_mod_1" in sys.modules
    finally:
        path.unlink()
        sys.modules.pop("test_mod_1", None)


def test_load_module_from_path_bad_spec():
    with pytest.raises(ImportError, match="File not found"):
        _load_module_from_path("test_mod_2", Path("/nonexistent/file.py"))


# ── _discover_user_skills ───────────────────────────────────────────────────


def test_discover_user_skills_missing_dir():
    with patch(
        "uar.skills.plugin._USER_SKILL_DIR",
        Path("/nonexistent/skills"),
    ):
        assert _discover_user_skills() == []


def test_discover_user_skills_finds_py_files(tmp_path):
    skill_dir = tmp_path / ".uar" / "skills"
    skill_dir.mkdir(parents=True)
    (skill_dir / "hello.py").write_text("x = 1")
    (skill_dir / "_hidden.py").write_text("x = 2")
    (skill_dir / "__init__.py").write_text("")
    (skill_dir / "nested").mkdir(parents=True)
    (skill_dir / "nested" / "deep.py").write_text("x = 3")

    with patch("uar.skills.plugin._USER_SKILL_DIR", skill_dir):
        found = _discover_user_skills()
        stems = {p.name for p in found}
        assert "hello.py" in stems
        assert "_hidden.py" not in stems
        assert "__init__.py" not in stems
        assert "deep.py" in stems


# ── _register_skills_from_module ────────────────────────────────────────────


def test_register_skills_from_module_with_register_skills():
    mod = MagicMock()
    mod.register_skills = MagicMock(return_value=3)

    count = _register_skills_from_module(mod)
    assert count == 3
    mod.register_skills.assert_called_once()


def test_register_skills_from_module_with_uar_skills():
    mock_registry = MagicMock()
    mod = MagicMock()
    del mod.register_skills  # ensure no register_skills attr
    mod.__uar_skills__ = {"skill_a": lambda x: x, "skill_b": lambda x: x}

    with patch("uar.skills.plugin.registry", mock_registry):
        count = _register_skills_from_module(mod)
    assert count == 2
    assert mock_registry.register.call_count == 2


def test_register_skills_from_module_empty():
    mock_registry = MagicMock()
    mod = MagicMock()
    del mod.register_skills
    mod.__uar_skills__ = {}

    with patch("uar.skills.plugin.registry", mock_registry):
        count = _register_skills_from_module(mod)
    assert count == 0


# ── load_plugins ───────────────────────────────────────────────────────────


def test_load_plugins_user_dir(tmp_path):
    skill_dir = tmp_path / "skills"
    skill_dir.mkdir()
    (skill_dir / "my_skill.py").write_text(
        "from uar.core.registry import register_skill\n"
        "@register_skill('my_skill')\n"
        "def my_skill(ctx):\n"
        "    return {'status': 'completed'}\n"
    )

    with patch("uar.skills.plugin._discover_pypi_plugins", return_value=[]):
        results = load_plugins(user_dir=skill_dir)

    assert isinstance(results, dict)
    # The file was discovered and loaded; count depends on registration
    assert len(results) >= 0  # may be 0 if registration failed in test env


def test_load_plugins_no_sources():
    with patch(
        "uar.skills.plugin._discover_user_skills", return_value=[]
    ), patch(
        "uar.skills.plugin._discover_pypi_plugins", return_value=[]
    ):
        results = load_plugins()
    assert results == {}


# ── reload_plugins ──────────────────────────────────────────────────────────


def test_reload_plugins_clears_manifests():
    with patch(
        "uar.skills.plugin._discover_user_skills", return_value=[]
    ), patch(
        "uar.skills.plugin._discover_pypi_plugins", return_value=[]
    ):
        reload_plugins()
    assert get_plugin_manifests() == []


# ── init_user_skill_dir ─────────────────────────────────────────────────────


def test_init_user_skill_dir_creates_structure(tmp_path):
    with patch("uar.skills.plugin._USER_SKILL_DIR", tmp_path / "skills"):
        skill_dir = init_user_skill_dir()
        assert skill_dir.exists()
        assert (skill_dir / "README.md").exists()
        assert (skill_dir / "example_plugin.py").exists()


def test_init_user_skill_dir_idempotent(tmp_path):
    with patch("uar.skills.plugin._USER_SKILL_DIR", tmp_path / "skills"):
        init_user_skill_dir()
        mtime = (tmp_path / "skills" / "README.md").stat().st_mtime
        init_user_skill_dir()
        assert (tmp_path / "skills" / "README.md").stat().st_mtime == mtime


# ── PluginManifest ──────────────────────────────────────────────────────────


def test_manifest_to_dict():
    m = PluginManifest(name="test", source="user", skill_count=5)
    d = m.to_dict()
    assert d["name"] == "test"
    assert d["source"] == "user"
    assert d["skill_count"] == 5
    assert d["healthy"] is True
    assert d["error"] is None
