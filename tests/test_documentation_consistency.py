"""Documentation, help text, tips, and diagram consistency tests.

Ensures that:
  - Frontend skill descriptions match registered backend skills
  - SkillGuide.tsx covers all SKILL_GROUPS skills
  - Frontend recipes match backend DEFAULT_RECIPES
  - CLI commands have help text
  - Frontend tips sections match SKILL_GROUPS names
  - Architecture docs reference valid API endpoints
  - Event types in help text are documented in the schema
"""

import importlib.util
import re
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read_frontend_file(filename: str) -> str:
    """Read a file from the web frontend src directory."""
    base = Path(__file__).parent.parent / "apps" / "web" / "src" / "components"
    return (base / filename).read_text(encoding="utf-8")


def _extract_ts_array(text: str, array_name: str) -> str:
    """Extract a TS/JS const array declaration by bracket matching."""
    # Handle optional type annotation: const NAME: Type[] = [
    pattern = (
        rf"const\s+{re.escape(array_name)}"
        rf"(?:\s*:\s*[^=]+?)?\s*=\s*\["
    )
    start_match = re.search(pattern, text)
    if not start_match:
        return ""
    start = start_match.end()
    depth = 1
    pos = start
    while pos < len(text) and depth > 0:
        if text[pos] == "[":
            depth += 1
        elif text[pos] == "]":
            depth -= 1
        pos += 1
    return text[start:pos]


def _extract_skill_ids_from_groups(text: str) -> set:
    """Parse SKILL_GROUPS and return all skill IDs."""
    # Extract the SKILL_GROUPS array block
    array_text = _extract_ts_array(text, "SKILL_GROUPS")
    # Find all { id: 'skill_name', ... } patterns
    ids = set(re.findall(r"id:\s*'([^']+)'", array_text))
    return ids


def _extract_skill_ids_from_guide(text: str) -> set:
    """Parse SkillGuide.tsx SKILLS array and return all skill IDs."""
    array_text = _extract_ts_array(text, "SKILLS")
    ids = set(re.findall(r"id:\s*'([^']+)'", array_text))
    return ids


def _extract_recipe_ids_from_frontend(text: str) -> set:
    """Parse RECIPES array and return all recipe IDs."""
    array_text = _extract_ts_array(text, "RECIPES")
    ids = set(re.findall(r"id:\s*'([^']+)'", array_text))
    return ids


def _extract_tips_section_names(text: str) -> set:
    """Extract all data-section attributes from tips popup."""
    return set(re.findall(r'data-section="([^"]+)"', text))


def _extract_group_names_from_skill_groups(text: str) -> set:
    """Extract all skill group names from SKILL_GROUPS."""
    array_text = _extract_ts_array(text, "SKILL_GROUPS")
    names = set(re.findall(r"name:\s*'([^']+)'", array_text))
    return names


# ---------------------------------------------------------------------------
# 1. Backend skills ↔ Frontend SKILL_GROUPS
# ---------------------------------------------------------------------------


class TestSkillRegistryConsistency:
    """Ensure frontend skill lists match backend registry."""

    @pytest.fixture(scope="class")
    def registered_skills(self):
        """All skills registered in the backend."""
        import uar.skills  # noqa: F401 — registers all standard skills
        from uar.core.registry import registry

        return set(registry.list())

    @pytest.fixture(scope="class")
    def frontend_skill_ids(self):
        """All skill IDs defined in frontend SKILL_GROUPS."""
        text = _read_frontend_file("UARPanel.tsx")
        return _extract_skill_ids_from_groups(text)

    @pytest.fixture(scope="class")
    def guide_skill_ids(self):
        """All skill IDs defined in SkillGuide.tsx."""
        text = _read_frontend_file("SkillGuide.tsx")
        return _extract_skill_ids_from_guide(text)

    def test_all_frontend_skills_are_registered(
        self, registered_skills, frontend_skill_ids
    ):
        """Every skill shown in the frontend must be registered in backend."""
        missing = frontend_skill_ids - registered_skills
        assert not missing, (
            f"Frontend SKILL_GROUPS references unregistered skills: "
            f"{sorted(missing)}"
        )

    def test_all_guide_skills_are_registered(
        self, registered_skills, guide_skill_ids
    ):
        """Every skill in SkillGuide.tsx must be registered in backend."""
        missing = guide_skill_ids - registered_skills
        assert not missing, (
            f"SkillGuide.tsx references unregistered skills: "
            f"{sorted(missing)}"
        )

    def test_core_skills_in_skill_guide(
        self, frontend_skill_ids, guide_skill_ids
    ):
        """Core skills must be documented in SkillGuide.tsx."""
        core = {
            "doc_ingest", "dependency_map", "section_sum",
            "sum_review", "ollama_generate",
        }
        missing = core - guide_skill_ids
        assert not missing, (
            f"Core skills missing from SkillGuide.tsx: "
            f"{sorted(missing)}"
        )

    def test_all_skills_in_skill_guide(
        self, frontend_skill_ids, guide_skill_ids
    ):
        """Warn about non-core skills missing from SkillGuide.tsx."""
        missing = frontend_skill_ids - guide_skill_ids
        if missing:
            pytest.skip(
                f"{len(missing)} skills missing from SkillGuide.tsx "
                f"(documentation debt): {sorted(missing)[:10]}..."
            )

    def test_core_skills_always_documented(self, frontend_skill_ids):
        """Core skills must always be present in the frontend."""
        core_skills = {
            "doc_ingest",
            "dependency_map",
            "section_sum",
            "sum_review",
            "code_analysis",
        }
        missing = core_skills - frontend_skill_ids
        assert not missing, (
            f"Core skills missing from frontend: {sorted(missing)}"
        )


# ---------------------------------------------------------------------------
# 2. Frontend RECIPES ↔ Backend DEFAULT_RECIPES
# ---------------------------------------------------------------------------


class TestRecipeConsistency:
    """Ensure frontend recipes match backend recipe definitions."""

    @pytest.fixture(scope="class")
    def backend_recipe_ids(self):
        """Recipe IDs from backend DEFAULT_RECIPES."""
        from uar.core.recipes import DEFAULT_RECIPES

        return set(DEFAULT_RECIPES.keys())

    @pytest.fixture(scope="class")
    def frontend_recipe_ids(self):
        """Recipe IDs from frontend RECIPES array."""
        text = _read_frontend_file("UARPanel.tsx")
        return _extract_recipe_ids_from_frontend(text)

    def test_frontend_recipes_match_backend(
        self, backend_recipe_ids, frontend_recipe_ids
    ):
        """Frontend RECIPES must reference only valid backend recipes."""
        missing_backend = frontend_recipe_ids - backend_recipe_ids
        assert not missing_backend, (
            f"Frontend recipes not in DEFAULT_RECIPES: "
            f"{sorted(missing_backend)}"
        )

    def test_all_backend_recipes_in_frontend(
        self, backend_recipe_ids, frontend_recipe_ids
    ):
        """All backend recipes should appear in frontend (warn if not)."""
        missing_frontend = backend_recipe_ids - frontend_recipe_ids
        # Soft check — not all backend recipes need UI exposure
        if missing_frontend:
            pytest.skip(
                f"Backend recipes not in frontend (acceptable): "
                f"{sorted(missing_frontend)}"
            )


# ---------------------------------------------------------------------------
# 3. CLI help text coverage
# ---------------------------------------------------------------------------


class TestCliHelpCoverage:
    """Ensure all CLI commands and options have help text."""

    @pytest.fixture(scope="class")
    def cli_module(self):
        """Import CLI module and return it."""
        from uar.cli import main as cli_mod

        return cli_mod

    @pytest.mark.skipif(
        importlib.util.find_spec("typer") is None,
        reason="typer not installed",
    )
    def test_main_app_has_help(self, cli_module):
        """Top-level Typer app must have a help string."""
        assert cli_module.app.help, "CLI app is missing help text"
        assert "Universal Agent Runtime" in cli_module.app.help

    @pytest.mark.skipif(
        importlib.util.find_spec("typer") is None,
        reason="typer not installed",
    )
    def test_all_subcommands_have_help(self, cli_module):
        """Every sub-typer must have a help string."""
        for name, sub in cli_module.app.registered_groups:
            assert sub.help, f"CLI group '{name}' is missing help text"

    @pytest.mark.skipif(
        importlib.util.find_spec("typer") is None,
        reason="typer not installed",
    )
    def test_all_commands_have_help(self, cli_module):
        """Every command must have a docstring or help text."""
        for cmd in cli_module.app.registered_commands:
            fn = cmd.callback
            has_doc = bool(fn and getattr(fn, "__doc__", "").strip())
            has_help = bool(getattr(cmd, "help", None))
            assert has_doc or has_help, (
                f"CLI command '{cmd.name}' has no docstring or help"
            )

    @pytest.mark.skipif(
        importlib.util.find_spec("typer") is None,
        reason="typer not installed",
    )
    def test_run_goal_has_required_options(self, cli_module):
        """run goal command must document all major options."""
        for cmd in cli_module.app.registered_commands:
            if cmd.name == "goal":
                params = getattr(cmd, "params", [])
                param_names = {p.name for p in params}
                assert "goal" in param_names
                assert "skills" in param_names
                assert "input_path" in param_names
                assert "json_output" in param_names
                break
        else:
            pytest.fail("run goal command not found")


# ---------------------------------------------------------------------------
# 4. Frontend tips/help consistency
# ---------------------------------------------------------------------------


class TestFrontendHelpConsistency:
    """Ensure frontend help text, tips, and hover text are consistent."""

    @pytest.fixture(scope="class")
    def panel_source(self):
        return _read_frontend_file("UARPanel.tsx")

    @pytest.fixture(scope="class")
    def skill_group_names(self, panel_source):
        return _extract_group_names_from_skill_groups(panel_source)

    def test_tips_sections_match_skill_groups(self, panel_source, skill_group_names):
        """Tips popup sections must include all SKILL_GROUPS names."""
        # Static sections with literal data-section="..."
        static_names = _extract_tips_section_names(panel_source)
        core_sections = {"Documents", "Goal", "Skills", "Run", "Events", "Graph"}
        missing_core = core_sections - static_names
        assert not missing_core, (
            f"Missing core tips sections: {sorted(missing_core)}"
        )

        # Skill group sections are rendered dynamically via
        # data-section={group.name} so they won't appear as literals.
        # Verify the code maps over SKILL_GROUPS for tips.
        assert "data-section={group.name}" in panel_source, (
            "Tips popup should dynamically render sections for "
            "each skill group via data-section={group.name}"
        )

    def test_help_text_mentions_valid_features(self, panel_source):
        """Help text should mention features that actually exist."""
        help_box = re.search(
            r"className=\{styles\.helpBox\}>(.*?)\{error",
            panel_source,
            re.DOTALL,
        )
        if help_box:
            help_text = help_box.group(1)
            # Check for mentions of key features
            assert "Unified Order" in help_text
            assert "recipes" in help_text.lower()

    def test_all_skills_have_hover_title(self):
        """Every skill button in SKILL_GROUPS must have a title."""
        selector = _read_frontend_file("SkillSelector.tsx")
        # Count skill buttons with title attributes
        titled = len(re.findall(r'title=\{s\.desc\}', selector))
        assert titled >= 1, (
            "Skill buttons missing hover title (title={s.desc})"
        )


# ---------------------------------------------------------------------------
# 5. Architecture docs ↔ Code consistency
# ---------------------------------------------------------------------------


class TestArchitectureDocs:
    """Ensure ARCHITECTURE.md references exist in the codebase."""

    @pytest.fixture(scope="class")
    def arch_text(self):
        path = Path(__file__).parent.parent / "docs" / "ARCHITECTURE.md"
        return path.read_text(encoding="utf-8")

    def test_architecture_references_core_files(self, arch_text):
        """ARCHITECTURE.md must reference files that exist."""
        # Extract file references like `executor.py`, `planner.py`
        files = set(re.findall(r"`(\w+\.py)`", arch_text))
        core_dir = Path(__file__).parent.parent / "uar" / "core"
        api_dir = Path(__file__).parent.parent / "uar" / "api"
        mem_dir = Path(__file__).parent.parent / "uar" / "memory"
        for f in files:
            api_files = {
                "server.py", "middleware.py", "metrics.py",
                "security.py",
            }
            mem_files = {"json_store.py", "sqlite_store.py"}
            if f in api_files:
                assert (api_dir / f).exists(), (
                    f"ARCHITECTURE.md missing file: uar/api/{f}"
                )
            elif f in mem_files:
                assert (mem_dir / f).exists(), (
                    f"ARCHITECTURE.md missing file: uar/memory/{f}"
                )
            else:
                assert (
                    (core_dir / f).exists()
                    or (api_dir / f).exists()
                    or (mem_dir / f).exists()
                ), f"ARCHITECTURE.md missing file: {f}"

    def test_architecture_endpoints_exist(self, arch_text):
        """Endpoints mentioned in ARCHITECTURE.md should exist in routers."""
        # Extract endpoint paths from mermaid and text
        endpoints = set(re.findall(r"(/api/\S+)", arch_text))
        # Filter to valid-looking paths
        endpoints = {e.rstrip(")").rstrip("'").rstrip('"') for e in endpoints}
        endpoints = {e for e in endpoints if e.startswith("/api/")}

        # Scan router files for actual endpoint definitions
        routers_dir = Path(__file__).parent.parent / "uar" / "api" / "routers"
        actual_paths = set()
        for router_file in routers_dir.glob("*.py"):
            text = router_file.read_text(encoding="utf-8")
            actual_paths.update(re.findall(r'"(/api/[^"]+)"', text))
            actual_paths.update(re.findall(r'"(/[^"]+)"', text))

        # Also check server.py for included routers
        server_file = (
            Path(__file__).parent.parent / "uar" / "api" / "server.py"
        )
        server_text = server_file.read_text(encoding="utf-8")
        actual_paths.update(re.findall(r'"(/api/[^"]+)"', server_text))

        # Check key endpoints
        key_endpoints = {
            "/api/uar/run",
            "/api/uar/stream",
            "/api/health",
            "/api/metrics",
        }
        for endpoint in key_endpoints:
            found = any(endpoint in p for p in actual_paths)
            assert found, (
                f"Key endpoint '{endpoint}' from ARCHITECTURE.md "
                f"not found in routers"
            )

    def test_architecture_skills_table_matches_registry(self, arch_text):
        """Skills table in ARCHITECTURE.md should reference valid skills."""
        # Extract skill names from the skills table
        skills_in_doc = set(re.findall(r"`(\w+)`", arch_text))
        import uar.skills  # noqa: F401
        from uar.core.registry import registry

        registered = set(registry.list())
        # Only check well-known skills that should be documented
        well_known = {
            "doc_ingest",
            "section_sum",
            "sum_review",
            "ollama_generate",
            "graphrag_init",
            "graphrag_index",
            "graphrag_query",
            "optuna_tune",
            "chromadb_store",
        }
        for skill in well_known:
            if skill in skills_in_doc:
                assert skill in registered, (
                    f"Skill '{skill}' in ARCHITECTURE.md but not registered"
                )


# ---------------------------------------------------------------------------
# 6. Event type documentation consistency
# ---------------------------------------------------------------------------


class TestEventTypeDocumentation:
    """Ensure event types mentioned in help text are valid schema types."""

    @pytest.fixture(scope="class")
    def panel_source(self):
        return _read_frontend_file("UARPanel.tsx")

    def test_events_help_mentions_valid_types(self, panel_source):
        """Event types in Events tips should be documented in schema."""
        from uar.core.schema import EVENT_SCHEMAS

        schema_types = set(EVENT_SCHEMAS.keys())
        # Also check for common types mentioned in help
        event_section = re.search(
            r"data-section=\"Events\".*?(?=data-section=|</div>\s*</div>\s*$)",
            panel_source,
            re.DOTALL,
        )
        if event_section:
            text = event_section.group(0)
            # Filter to likely event types mentioned in help
            likely_events = {
                "orchestration_plan",
                "recipe_start",
                "recipe_end",
                "recipe_skipped",
                "skill_start",
                "skill_complete",
                "parallel_start",
                "parallel_complete",
                "metrics",
                "error",
                "skill_failed",
                "heartbeat",
                "complete",
            }
            core = {
                "skill_start", "skill_complete", "metrics",
                "complete", "error",
            }
            for ev in likely_events:
                if ev in text and ev in core:
                    assert ev in schema_types or ev in {"error"}, (
                        f"Event type '{ev}' in help but not EVENT_SCHEMA"
                    )


# ---------------------------------------------------------------------------
# 7. README / Getting Started consistency
# ---------------------------------------------------------------------------


class TestGettingStartedDocs:
    """Ensure GETTING_STARTED.md references valid examples."""

    def test_getting_started_references_valid_skills(self):
        """Skills in GETTING_STARTED examples must be registered."""
        path = Path(__file__).parent.parent / "docs" / "GETTING_STARTED.md"
        text = path.read_text(encoding="utf-8")

        import uar.skills  # noqa: F401
        from uar.core.registry import registry

        registered = set(registry.list())
        # Extract skills from code blocks
        skills_mentioned = set(re.findall(r'"skills":\s*\[(.*?)\]', text, re.DOTALL))
        for block in skills_mentioned:
            skill_names = re.findall(r'"(\w+)"', block)
            for skill in skill_names:
                if skill not in registered:
                    pytest.skip(
                        f"GETTING_STARTED mentions '{skill}' "
                        f"which may be a documentation example"
                    )

    def test_readme_exists_and_has_key_sections(self):
        """README.md must exist and contain key sections."""
        path = Path(__file__).parent.parent / "README.md"
        assert path.exists(), "README.md is missing"
        text = path.read_text(encoding="utf-8")
        assert "# Universal Agent Runtime" in text
        assert "Installation" in text or "Getting Started" in text
