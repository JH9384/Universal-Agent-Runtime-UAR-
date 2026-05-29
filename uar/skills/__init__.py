"""UAR built-in skills.

Importing this module registers all standard skills in the global
``SkillRegistry``. Eliminates the duplicated import blocks that existed
across CLI, API server, MCP server, and tests.

Usage::

    import uar.skills  # noqa: F401  — registers everything
"""

# Core / foundational skills
import uar.skills.section_sum  # noqa: F401
import uar.skills.doc_ingest  # noqa: F401
import uar.skills.doc_ingest_enhanced  # noqa: F401
import uar.skills.dependency_map  # noqa: F401
import uar.skills.sum_review  # noqa: F401
import uar.skills.code_analysis  # noqa: F401
import uar.skills.cipher_ops  # noqa: F401

# Math & STEM
import uar.skills.math_compute  # noqa: F401
import uar.skills.math_plot  # noqa: F401
import uar.skills.math_plot_3d  # noqa: F401
import uar.skills.physics_compute  # noqa: F401
import uar.skills.stem_extended  # noqa: F401
import uar.skills.data_viz_3d  # noqa: F401

# LLM providers (OpenAI-compatible via llm_base)
import uar.skills.openai_skills  # noqa: F401
import uar.skills.groq_skills  # noqa: F401
import uar.skills.together_skills  # noqa: F401
import uar.skills.huggingface_skills  # noqa: F401
import uar.skills.lm_studio_skills  # noqa: F401
import uar.skills.mistral_skills  # noqa: F401

# LLM providers (native SDKs)
import uar.skills.anthropic_skills  # noqa: F401
import uar.skills.gemini_skills  # noqa: F401

# Specialized / advanced
import uar.skills.ollama_generate  # noqa: F401
import uar.skills.graphrag_skills  # noqa: F401
import uar.skills.autonomi_storage  # noqa: F401
import uar.skills.atomic_lang_model  # noqa: F401
import uar.skills.advanced_integrations  # noqa: F401
import uar.skills.uor_ecosystem_skills  # noqa: F401
import uar.skills.trefoil_simulation  # noqa: F401
import uar.skills.molecular_visualization  # noqa: F401
import uar.skills.quantum_circuit_visualization  # noqa: F401
import uar.skills.riscv_sim  # noqa: F401
import uar.skills.verilog_parse  # noqa: F401
import uar.skills.fpga_verify  # noqa: F401
import uar.skills.myhdl_design  # noqa: F401
import uar.skills.riscv_cycle  # noqa: F401
import uar.skills.verilator_sim  # noqa: F401
import uar.skills.micropython  # noqa: F401
import uar.skills.platformio  # noqa: F401
import uar.skills.cv_skills  # noqa: F401
import uar.skills.ml_tools  # noqa: F401
import uar.skills.quantum_ml  # noqa: F401
import uar.skills.cern_root  # noqa: F401

# Aliases (must be before stubs so they override stub registrations)
import uar.skills.alias_skills  # noqa: F401

# Stubs (must be last so real implementations take precedence)
import uar.skills.stub_skills  # noqa: F401
