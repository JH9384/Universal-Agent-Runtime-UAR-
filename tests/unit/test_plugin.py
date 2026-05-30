"""Tests for uar.skills.plugin."""

from unittest.mock import MagicMock, patch

from uar.skills.plugin import (
    _discover_user_skills,
    _discover_pypi_plugins,
    _register_skills_from_module,
    load_plugins,
    init_user_skill_dir,
)


class TestDiscoverUserSkills:
    def test_no_dir(self):
        with patch(
            "uar.skills.plugin._USER_SKILL_DIR",
            MagicMock(exists=MagicMock(return_value=False)),
        ):
            result = _discover_user_skills()
        assert result == []

    def test_discovers(self, tmp_path):
        skill_dir = tmp_path / ".uar" / "skills"
        skill_dir.mkdir(parents=True)
        (skill_dir / "test_skill.py").write_text("# skill")
        (skill_dir / "_hidden.py").write_text("# hidden")
        (skill_dir / "__init__.py").write_text("")
        with patch("uar.skills.plugin._USER_SKILL_DIR", skill_dir):
            result = _discover_user_skills()
        assert len(result) == 1
        assert result[0].name == "test_skill.py"


class TestDiscoverPypiPlugins:
    def test_empty(self):
        with patch(
            "importlib.metadata.entry_points",
            side_effect=Exception("fail"),
        ):
            result = _discover_pypi_plugins()
        assert result == []

    def test_legacy_api(self):
        eps = {"uar.skills": [MagicMock()]}
        mock_ep = MagicMock()
        mock_ep.load.return_value = "mod"
        eps["uar.skills"][0] = mock_ep
        with patch("importlib.metadata.entry_points") as mock_eps:
            mock_eps.return_value = eps
            result = _discover_pypi_plugins()
        assert result == ["mod"]


class TestRegisterSkills:
    def test_no_skills(self):
        mod = MagicMock()
        mod.__uar_skills__ = {}
        assert _register_skills_from_module(mod) == 0

    def test_with_register_skills(self):
        mod = MagicMock()
        mod.register_skills.return_value = 2
        assert _register_skills_from_module(mod) == 2

    def test_with_uar_skills(self):
        mod = MagicMock()
        del mod.register_skills
        mod.__uar_skills__ = {"s1": lambda x: x}
        with patch("uar.skills.plugin.registry"):
            count = _register_skills_from_module(mod)
        assert count == 1


class TestLoadPlugins:
    def test_empty(self):
        with patch(
            "uar.skills.plugin._discover_user_skills", return_value=[]
        ):
            with patch(
                "uar.skills.plugin._discover_pypi_plugins",
                return_value=[],
            ):
                result = load_plugins()
        assert result == {}

    def test_with_user_dir(self, tmp_path):
        skill_dir = tmp_path / "skills"
        skill_dir.mkdir()
        f = skill_dir / "test.py"
        f.write_text("x = 1")
        with patch(
            "uar.skills.plugin._discover_user_skills",
            return_value=[f],
        ):
            with patch(
                "uar.skills.plugin._load_module_from_path",
                return_value=MagicMock(),
            ):
                with patch(
                    "uar.skills.plugin._register_skills_from_module",
                    return_value=1,
                ):
                    result = load_plugins(user_dir=skill_dir)
        assert result == {"test.py": 1}


class TestInitUserSkillDir:
    def test_creates_dir(self, tmp_path):
        skill_dir = tmp_path / ".uar" / "skills"
        with patch("uar.skills.plugin._USER_SKILL_DIR", skill_dir):
            result = init_user_skill_dir()
        assert result.exists()
        assert (result / "README.md").exists()
        assert (result / "example_plugin.py").exists()

    def test_skips_existing(self, tmp_path):
        skill_dir = tmp_path / ".uar" / "skills"
        skill_dir.mkdir(parents=True)
        (skill_dir / "README.md").write_text("existing")
        (skill_dir / "example_plugin.py").write_text("existing")
        with patch("uar.skills.plugin._USER_SKILL_DIR", skill_dir):
            result = init_user_skill_dir()
        assert (result / "README.md").read_text() == "existing"
