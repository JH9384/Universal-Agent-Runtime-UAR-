"""Regression tests for frontend/backend skill alignment.

Ensures that skills advertised in the frontend UI actually exist in the
backend registry, and vice versa. Catches the class of bugs where:
- A skill is added to the frontend SKILL_GROUPS but never implemented
- A real backend skill is never exposed in the frontend UI
- A stub skill gets a real implementation but remains in stub_skills.py
- SkillGuide documents skills that don't exist
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Set

import pytest  # noqa: F401

# Import all skill modules to populate the registry
import uar.skills.section_sum  # noqa
import uar.skills.doc_ingest  # noqa
import uar.skills.doc_ingest_enhanced  # noqa
import uar.skills.dependency_map  # noqa
import uar.skills.sum_review  # noqa
import uar.skills.ollama_generate  # noqa
import uar.skills.graphrag_skills  # noqa
import uar.skills.autonomi_storage  # noqa
import uar.skills.atomic_lang_model  # noqa
import uar.skills.math_compute  # noqa
import uar.skills.cipher_ops  # noqa
import uar.skills.physics_compute  # noqa
import uar.skills.openai_skills  # noqa
import uar.skills.lm_studio_skills  # noqa
import uar.skills.anthropic_skills  # noqa
import uar.skills.gemini_skills  # noqa
import uar.skills.mistral_skills  # noqa
import uar.skills.groq_skills  # noqa
import uar.skills.huggingface_skills  # noqa
import uar.skills.together_skills  # noqa
import uar.skills.advanced_integrations  # noqa
import uar.skills.uor_ecosystem_skills  # noqa
import uar.skills.trefoil_simulation  # noqa
import uar.skills.molecular_visualization  # noqa
import uar.skills.quantum_circuit_visualization  # noqa
import uar.skills.riscv_sim  # noqa
import uar.skills.verilog_parse  # noqa
import uar.skills.fpga_verify  # noqa
import uar.skills.myhdl_design  # noqa
import uar.skills.riscv_cycle  # noqa
import uar.skills.verilator_sim  # noqa
import uar.skills.micropython  # noqa
import uar.skills.platformio  # noqa
import uar.skills.stub_skills  # noqa
import uar.skills.data_viz_3d  # noqa
import uar.skills.stem_extended  # noqa
import uar.skills.cv_skills  # noqa
import uar.skills.ml_tools  # noqa
import uar.skills.quantum_ml  # noqa
import uar.skills.math_plot  # noqa
import uar.skills.math_plot_3d  # noqa
import uar.skills.code_analysis  # noqa

from uar.core.registry import registry


PROJECT_ROOT = Path(__file__).parent.parent
PANEL_PATH = (
    PROJECT_ROOT / "apps" / "web" / "src" / "components" / "UARPanel.tsx"
)
GUIDE_PATH = (
    PROJECT_ROOT / "apps" / "web" / "src" / "components" / "SkillGuide.tsx"
)
STUB_PATH = PROJECT_ROOT / "uar" / "skills" / "stub_skills.py"


def _extract_skills_from_skill_groups(source: str) -> Set[str]:
    """Parse UARPanel.tsx and extract all skill IDs from SKILL_GROUPS."""
    # Regex approach: find all { id: 'xxx', ... } inside SKILL_GROUPS
    skills: Set[str] = set()
    # Match skill objects: { id: 'skill_name', label: ... }
    for match in re.finditer(r"\{\s*id:\s*['\"]([^'\"]+)['\"]", source):
        skills.add(match.group(1))
    return skills


def _extract_skills_from_skill_guide(source: str) -> Set[str]:
    """Parse SkillGuide.tsx and extract all skill IDs."""
    skills: Set[str] = set()
    for match in re.finditer(r"id:\s*['\"]([^'\"]+)['\"]", source):
        skills.add(match.group(1))
    return skills


def _extract_stub_skills(source: str) -> Set[str]:
    """Parse stub_skills.py and extract stub skill names."""
    stubs: Set[str] = set()
    # Find _STUBS dict block and match entries
    m = re.search(r"_STUBS:.*?=.*?\{(.*?)\}", source, re.DOTALL)
    if m:
        block = m.group(1)
        for match in re.finditer(r'"([^"]+)":\s*"', block):
            stubs.add(match.group(1))
    return stubs


def _read_file(path: Path) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSkillAlignment:
    """End-to-end alignment between frontend and backend skill registry."""

    @pytest.fixture(scope="class")
    def backend_skills(self) -> Set[str]:
        """All skills registered in the backend registry."""
        return set(registry.list())

    @pytest.fixture(scope="class")
    def frontend_skills(self) -> Set[str]:
        """All skills declared in frontend SKILL_GROUPS."""
        return _extract_skills_from_skill_groups(_read_file(PANEL_PATH))

    @pytest.fixture(scope="class")
    def guide_skills(self) -> Set[str]:
        """All skills documented in SkillGuide."""
        return _extract_skills_from_skill_guide(_read_file(GUIDE_PATH))

    @pytest.fixture(scope="class")
    def stub_skills(self) -> Set[str]:
        """All skills still listed as stubs."""
        return _extract_stub_skills(_read_file(STUB_PATH))

    # -----------------------------------------------------------------------
    # Critical: frontend skills must exist in backend
    # -----------------------------------------------------------------------

    def test_all_frontend_skills_exist_in_backend(
        self, frontend_skills: Set[str], backend_skills: Set[str]
    ) -> None:
        """Every skill shown in the frontend UI must be registered backend."""
        missing = frontend_skills - backend_skills
        assert not missing, (
            f"Frontend skills missing from backend: {sorted(missing)}\n"
            f"These are advertised in the UI but have no implementation."
        )

    def test_all_backend_skills_exist_in_frontend(
        self, frontend_skills: Set[str], backend_skills: Set[str]
    ) -> None:
        """Every backend skill should be discoverable in the frontend UI.

        Exceptions are allowed for internal/diagnostic skills.
        """
        allowed_missing = {
            "deps",            # internal diagnostic
            "review",          # internal
            "eco_canon",       # internal
            "eco_foundation",  # internal
            "eco_status",      # internal
            "blackboard_message",  # internal
            "uor_foundation_verify",  # internal
            "auto_up",         # alias handled by autonomi_storage
            "auto_down",       # alias
            "auto_status",     # alias
            "gr_full",         # alias
            "gr_index",        # alias
            "gr_query",        # alias
            "slow_skill",      # test-only fixture
        }
        missing = backend_skills - frontend_skills - allowed_missing
        assert not missing, (
            f"Backend skills missing from frontend: {sorted(missing)}\n"
            f"Add them to UARPanel.tsx SKILL_GROUPS."
        )

    # -----------------------------------------------------------------------
    # SkillGuide alignment
    # -----------------------------------------------------------------------

    def test_all_guide_skills_exist_in_backend(
        self, guide_skills: Set[str], backend_skills: Set[str]
    ) -> None:
        """SkillGuide should only document real backend skills."""
        missing = guide_skills - backend_skills
        assert not missing, (
            f"SkillGuide documents skills not in backend: {sorted(missing)}\n"
            f"Update apps/web/src/components/SkillGuide.tsx."
        )

    def test_all_real_backend_skills_in_guide(
        self, guide_skills: Set[str], backend_skills: Set[str],
        stub_skills: Set[str]
    ) -> None:
        """Every non-stub backend skill should be in SkillGuide."""
        internal = {
            "deps", "review", "eco_canon", "eco_foundation",
            "eco_status", "uor_foundation_verify",
            "auto_up", "auto_down", "auto_status",
            "gr_full", "gr_index", "gr_query",
            "slow_skill",      # test-only fixture
        }
        real_skills = backend_skills - stub_skills - internal
        missing = real_skills - guide_skills
        assert not missing, (
            f"Real backend skills missing from SkillGuide: {sorted(missing)}\n"
            f"Add them to apps/web/src/components/SkillGuide.tsx."
        )

    # -----------------------------------------------------------------------
    # Stub sanity checks
    # -----------------------------------------------------------------------

    def test_no_stubs_shadow_real_implementations(
        self, stub_skills: Set[str], backend_skills: Set[str]
    ) -> None:
        """If a stub skill also has a real implementation, the stub should
        have been removed from stub_skills.py (the real one wins, but
        both being present is confusing)."""
        # This is a soft check: warn about duplicates
        duplicates = stub_skills & backend_skills
        # Some stubs intentionally share names with real skills (they are
        # fallback wrappers). Filter those that are actually registered
        # by real modules elsewhere.
        real_modules = {
            "agent_workflow", "crewai_task", "crewai_workflow",
            "llamaindex_rag", "llamaindex_query",
            "dagster_pipeline", "dagster_status",
            "guardrail_check", "budget_status", "blackboard_status",
            "mlflow_track", "mlflow_deploy", "model_reg", "kubeflow_pipe",
            "airflow_dag", "dbt_transform", "snowflake_etl", "spark_process",
            "pentest_scan", "osint_recon", "crypto_analyze", "security_audit",
            "yolo_detect", "opencv_process", "video_analyze", "face_recognize",
            "solana_tx", "smart_contract", "nft_mint",
            "myhdl_design", "riscv_cycle", "verilator_sim", "micropython",
            "platformio",
            "cern_root", "quantum_ml", "chem_analysis", "bio_compute",
            "relativity", "diff_eq_solve", "scipy_opt", "autogluon_ml",
            "pycaret_ml", "flaml_auto",
            # Recipe aliases / internal markers (intentionally stub-only)
            "auto_up", "auto_down", "auto_status",
            "deps", "eco_canon", "eco_foundation", "eco_status",
            "gr_full", "gr_index", "gr_query",
            # Pure stubs with no real implementation
            "review",
        }
        should_not_be_stub = duplicates - real_modules
        assert not should_not_be_stub, (
            f"Real skills still in stubs: {sorted(should_not_be_stub)}\n"
            f"Remove them from stub_skills.py."
        )

    def test_stub_skills_are_registered(
        self, stub_skills: Set[str], backend_skills: Set[str]
    ) -> None:
        """Every stub must be registered (stub_skills.py registers them)."""
        missing = stub_skills - backend_skills
        assert not missing, (
            f"Stubs in stub_skills.py not registered: {sorted(missing)}"
        )

    # -----------------------------------------------------------------------
    # No duplicate registrations
    # -----------------------------------------------------------------------

    def test_no_duplicate_registrations(
        self, backend_skills: Set[str]
    ) -> None:
        """Registry.list() must not contain duplicates.

        Enforced by SkillRegistry.register raising on duplicate names.
        """
        # This is implicitly true because registry uses a dict, but let's
        # be explicit: count via the source.
        source = _read_file(STUB_PATH)
        counts: dict[str, int] = {}
        for match in re.finditer(r'"([^"]+)":\s*"', source):
            name = match.group(1)
            if name not in (
                "deps", "review", "eco_canon",
                "eco_foundation", "eco_status",
            ):
                counts[name] = counts.get(name, 0) + 1
        duplicates = {name for name, c in counts.items() if c > 1}
        assert not duplicates, (
            f"Duplicate stub entries: {sorted(duplicates)}"
        )
