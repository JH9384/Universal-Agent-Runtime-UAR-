# UAR Skill Audit — May 29, 2026

## Executive Summary

Audit of **17 UI skill groups** against actual backend implementations.

- **Real skills**: ~50 (fully implemented, do what they claim)
- **Stub/placeholder skills**: ~45 (dependency-check wrappers only)
- **Cosplay skills**: ~8 (branded as external frameworks, actually UAR-native)
- **Total registered**: 127 skills (per BOOT_CAPTURE.md)

---

## 1. Core UAR — FULLY REAL ✅

| Skill | File | Status | Evidence |
|-------|------|--------|----------|
| `doc_ingest` | `uar/skills/doc_ingest.py` | ✅ Real | Path validation, security checks, 30+ file types, size limits |
| `doc_ingest_enhanced` | `uar/skills/doc_ingest_enhanced.py` | ✅ Real | Delegates to unstructured/docling with fallback |
| `dependency_map` | `uar/skills/dependency_map.py` | ✅ Real | Builds artifact dependency graphs |
| `section_sum` | `uar/skills/section_sum.py` | ✅ Real | Document summarization |
| `sum_review` | `uar/skills/sum_review.py` | ✅ Real | Pipeline output review |
| `code_analysis` | `uar/skills/code_analysis.py` | ✅ Real | Multi-language static analysis |

---

## 2. AI / LLM — MIXED ⚠️

| Skill | Status | Evidence |
|-------|--------|----------|
| `ollama_generate` | ✅ Real | Circuit breaker, doc context, HTTP calls to Ollama |
| `openai_chat/completion/embedding` | ✅ Real | `llm_base.py` factory, needs API key |
| `anthropic_*`, `gemini_*`, `mistral_*`, `groq_*`, `huggingface_*`, `together_*`, `lm_studio_*` | ✅ Real | Shared `register_openai_provider` factory |
| `optuna_tune` | ❌ Stub | `stub_skills.py` |
| `autogluon_ml` | ❌ Stub | `stub_skills.py` |
| `pycaret_ml` | ❌ Stub | `stub_skills.py` |
| `flaml_auto` | ❌ Stub | `stub_skills.py` |
| `chromadb_store` | ❌ Stub | `stub_skills.py` |

---

## 3. Multi-Agent — THEATER ❌

| Skill | Status | Evidence |
|-------|--------|----------|
| `agent_workflow` | ❌ Cosplay | Uses UAR's own `Agent` class, not AutoGen |
| `crewai_task` | ❌ Cosplay | Uses UAR's `RoleBasedAgent`, not CrewAI library |
| `crewai_workflow` | ❌ Cosplay | Same — CrewAI terminology on UAR-native code |

**Files**: `uar/core/crewai_integration.py`, `uar/core/agent_framework.py`, `uar/skills/advanced_integrations.py`

---

## 4. Advanced RAG — THEATER ❌

| Skill | Status | Evidence |
|-------|--------|----------|
| `llamaindex_rag` | ❌ Stub | Imports `LlamaIndexRAG` from `uar.core.llamaindex_rag` |
| `llamaindex_query` | ❌ Stub | Same — minimal/no real implementation |

---

## 5. Pipeline Orchestration — THEATER ❌

| Skill | Status | Evidence |
|-------|--------|----------|
| `dagster_pipeline` | ❌ Stub | Checks for `dagster` package |
| `dagster_status` | ❌ Stub | Availability check only |

---

## 6. Governance — MIXED ⚠️

| Skill | Status | Evidence |
|-------|--------|----------|
| `guardrail_check` | ✅ Real | `_validate_input_guardrails`, `_validate_output_guardrails` in executor |
| `budget_status` | ⚠️ Partial | `guardrails.py` exists, enforcement superficial |
| `blackboard_status/message` | ⚠️ Partial | Part of agent framework, lightly tested |

---

## 7. GraphRAG — FULLY REAL ✅

| Skill | File | Status |
|-------|------|--------|
| `graphrag_init` | `uar/skills/graphrag_skills.py` | ✅ Real |
| `graphrag_index` | `uar/skills/graphrag_skills.py` | ✅ Real |
| `graphrag_query` | `uar/skills/graphrag_skills.py` | ✅ Real |
| `flexible_graphrag` | `uar/skills/advanced_integrations.py` | ⚠️ Stub |

**Tests**: `tests/skills/test_graphrag_skills.py`

---

## 8. Autonomi — FULLY REAL ✅

| Skill | File | Status |
|-------|------|--------|
| `autonomi_upload` | `uar/skills/autonomi_storage.py` | ✅ Real |
| `autonomi_download` | `uar/skills/autonomi_storage.py` | ✅ Real |
| `autonomi_status` | `uar/skills/autonomi_storage.py` | ✅ Real |

**Notes**: Calls actual autonomi SDK. Fixed `asyncio.run()` bug in Session 5.

---

## 9. ALM — THEATER ❌

| Skill | Status |
|-------|--------|
| `alm_analyze` | ❌ Stub |
| `alm_generate` | ❌ Stub |
| `alm_verify` | ❌ Stub |

---

## 10. UOR Ecosystem — MIXED ⚠️

| Skill | Status | Evidence |
|-------|--------|----------|
| `uor_addr_canonicalize` | ✅ Real | Calls `eco.uor_addr.canonicalize()` |
| `uor_addr_resolve` | ✅ Real | Digest cache lookup |
| `hologram_query/status` | ✅ Real | HTTP to gethologram.ai |
| `moltbook_list/search/post` | ✅ Real | HTTP to moltbook forum |
| `prism_btc_anchor/verify` | ❌ Placeholder | Docstring: "pending public API" |
| `severance_infer/verify` | ❌ Placeholder | Docstring: "pending public API" |
| `anunix_health/run` | ❌ Placeholder | Docstring: "pending public API" |
| `uor_ecosystem_status` | ✅ Real | Aggregates all health |

---

## 11. STEM — MOSTLY REAL ✅

| Skill | Status | Evidence |
|-------|--------|----------|
| `math_compute` | ✅ Real | SymPy wrapper |
| `math_plot` | ✅ Real | matplotlib 2D |
| `math_plot_3d` | ✅ Real | matplotlib 3D |
| `cipher_ops` | ✅ Real | PyCryptodome: AES, SHA256, Ed25519 |
| `physics_compute` | ✅ Real | Astropy: units, coords, cosmology |
| `diff_eq_solve` | ❌ Stub | requires `diffeqpy` |
| `cern_root` | ❌ Stub | requires `uproot` |
| `scipy_opt` | ❌ Stub | requires `scipy` |
| `quantum_circuit` | ❌ Stub | requires `qiskit` |
| `quantum_ml` | ❌ Stub | requires `pennylane` |
| `chem_analysis` | ❌ Stub | requires `rdkit` |
| `bio_compute` | ❌ Stub | requires `biopython` |
| `relativity` | ❌ Stub | requires `einsteinpy` |
| `data_viz_3d` | ❌ Stub | requires `pyvista` |
| `trefoil_simulation` | ✅ Real | Pure numpy quaternion math |
| `molecular_visualization` | ✅ Real | Hardcoded 3D coords |
| `quantum_circuit_visualization` | ✅ Real | Pure Python 3D layout |

---

## 12. Hardware / Embedded — MIXED ⚠️

| Skill | Status |
|-------|--------|
| `fpga_verify` | ❌ Stub (requires `cocotb`) |
| `verilog_parse` | ❌ Stub (requires `pyverilog`) |
| `myhdl_design` | ⚠️ Partial |
| `riscv_sim` | ✅ Real — pure Python RV32I emulator |
| `riscv_cycle` | ❌ Stub |
| `verilator_sim` | ❌ Stub |
| `micropython` | ❌ Stub |
| `platformio` | ❌ Stub |

---

## 13. Computer Vision — ALL STUBS ❌

| Skill | Status |
|-------|--------|
| `yolo_detect` | ❌ Stub |
| `opencv_process` | ❌ Stub |
| `video_analyze` | ❌ Stub |
| `face_recognize` | ❌ Stub |

---

## 14. Blockchain / Web3 — ALL STUBS ❌

| Skill | Status |
|-------|--------|
| `solana_tx` | ❌ Stub |
| `smart_contract` | ❌ Stub |
| `nft_mint` | ❌ Stub |

---

## 15. MLOps — ALL STUBS ❌

| Skill | Status |
|-------|--------|
| `mlflow_track` | ❌ Stub |
| `mlflow_deploy` | ❌ Stub |
| `kubeflow_pipe` | ❌ Stub |
| `model_reg` | ❌ Stub |

---

## 16. Security — ALL STUBS ❌

| Skill | Status |
|-------|--------|
| `pentest_scan` | ❌ Stub |
| `osint_recon` | ❌ Stub |
| `crypto_analyze` | ❌ Stub |
| `security_audit` | ❌ Stub |

---

## 17. Data Engineering — ALL STUBS ❌

| Skill | Status |
|-------|--------|
| `airflow_dag` | ❌ Stub |
| `dbt_transform` | ❌ Stub |
| `snowflake_etl` | ❌ Stub |
| `spark_process` | ❌ Stub |

---

## Stub Skills Registry

From `uar/skills/stub_skills.py`:

```python
_STUBS = {
    "airflow_dag": "apache-airflow",
    "auto_down": "autonomi",
    "auto_status": "autonomi",
    "auto_up": "autonomi",
    "autogluon_ml": "autogluon",
    "cern_root": "uproot",
    "crypto_analyze": "pycryptodome",
    "dbt_transform": "dbt-core",
    "deps": "",            # recipe stub
    "eco_canon": "",        # ecosystem stub
    "eco_foundation": "",   # ecosystem stub
    "eco_status": "",       # ecosystem stub
    "face_recognize": "face-recognition",
    "flaml_auto": "flaml",
    "gr_full": "graphrag",
    "gr_index": "graphrag",
    "gr_query": "graphrag",
    "kubeflow_pipe": "kfp",
    "mlflow_deploy": "mlflow",
    "mlflow_track": "mlflow",
    "model_reg": "mlflow",
    "nft_mint": "web3",
    "osint_recon": "shodan",
    "pentest_scan": "python-nmap",
    "pycaret_ml": "pycaret",
    "review": "",           # recipe stub
    "security_audit": "bandit",
    "smart_contract": "web3",
    "snowflake_etl": "snowflake-connector-python",
    "solana_tx": "solana",
    "spark_process": "pyspark",
    "video_analyze": "moviepy",
}
```

---

## Recommendations

1. **Remove or hide stub-only groups** from the UI until they have real implementations
2. **Add `(stub)` badges** in the UI for skills that are dependency-check placeholders
3. **Prioritize completing STEM stubs** (scipy, qiskit, rdkit, biopython) — they have the highest utility-to-effort ratio
4. **Fix Multi-Agent cosplay** — either wire real CrewAI/AutoGen or rename to "UAR Agent Patterns"
5. **Fix Advanced RAG** — LlamaIndex integration needs actual implementation

---

*Audit performed by chaos rider — May 29, 2026*
