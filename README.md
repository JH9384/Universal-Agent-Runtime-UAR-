# Universal Agent Runtime (UAR) v1.1.0

UOR-aligned agent execution layer for modular goal-driven agent workflows.

## Features

- **Modular Runtime**: Extensible skill-based execution engine
- **Event Streaming**: Real-time execution monitoring via Server-Sent Events
- **Hierarchical Execution**: Recipes as discrete nested units with snapshot/retry/params scoping
- **Recipe-Level Caching**: Context mutations cached per recipe ID and parameters
- **Document Processing**: Multi-format ingestion (PDF, DOCX, XLSX, Jupyter, etc.)
- **API Server**: Production-ready FastAPI server with security middleware
- **Web Interface**: React-based control surface for workflow visualization
- **UOR Ecosystem Integration**: Live API clients for UOR Foundation, Hologram, Moltbook, and more
- **Replay & Persistence**: JSONL-based run storage with event reconstruction
- **Security**: Path validation, rate limiting, input sanitization, SSRF prevention

## Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+ (for web interface)
- Docker (optional)

### Tested Environments

UAR has been tested and validated on the following environments:

**Python Versions:**
- Python 3.10
- Python 3.11
- Python 3.12

**Operating Systems:**
- macOS (Apple Silicon and Intel)
- Linux (Ubuntu 22.04, Debian 12)
- Windows 11 (via WSL2)

**Dependencies:**
- FastAPI 0.110.0
- Pydantic 2.0+
- uvicorn 0.24.0+
- rfc8785 >=0.1.0

**Optional Integrations:**
- Ollama 0.1.0+ (for local LLM inference)
- GraphRAG 0.3.0+ (for knowledge graph operations)
- Autonomi Python SDK (experimental, network-dependent)

**Note:** Autonomi integration is marked as experimental due to network stability and SDK maturity issues. Use with caution in production environments.

### Installation

UAR offers multiple installation options depending on your use case. The base installation is lightweight (~100MB), while optional integrations can be added as needed.

#### Base Installation (Recommended for Getting Started)

```bash
# Clone repository
git clone https://github.com/JH9384/Universal-Agent-Runtime-UAR-.git
cd Universal-Agent-Runtime-UAR-

# Install base dependencies (core functionality only)
pip install -e .

# Install web dependencies (optional)
cd apps/web
npm install
npm run build
```

**Includes:** Core runtime, document processing (basic), API server, CLI tools

#### Full Installation (All Advanced Integrations)

```bash
# Install with all advanced integrations
pip install -e ".[advanced]"
```

**Includes:** All base features + AutoGen, CrewAI, LlamaIndex, Dagster, Neo4j, ChromaDB, Qdrant, Docling, Unstructured

#### Selective Installation (By Feature)

```bash
# Document processing (PDF, DOCX, images, tables)
pip install -e ".[doc-processing]"

# Agent orchestration (multi-agent workflows)
pip install -e ".[agent-orchestration]"

# Advanced RAG (knowledge graphs, vector databases)
pip install -e ".[advanced-rag]"

# Pipeline orchestration (Dagster workflows)
pip install -e ".[pipeline-orchestration]"

# GraphRAG (knowledge graph operations)
pip install -e ".[graphrag]"

# Autonomi (decentralized storage - experimental)
pip install -e ".[autonomi]"
```

#### Development Installation

```bash
# Install with development tools
pip install -e ".[dev]"
```

### Run Locally

```bash
# Start API server
python -m uvicorn uar.api.server:app --host 127.0.0.1 --port 8000

# Open API docs
open http://127.0.0.1:8000/docs

# Start web interface
cd apps/web && npm run dev
```

### Basic Usage

```python
from uar.api.server import app
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor

# Example goal execution
goal = {"goal": "Summarize this document", "input_path": "docs/README.md"}
# Use API endpoints or direct execution
```

## Available Skills

**124 skills registered** across 9 categories. Skills marked with **(stub)** are
placeholder wrappers that check for optional dependencies and return availability
status. All others are fully implemented.

### Document Processing

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `doc_ingest` | Multi-format document ingestion (PDF, DOCX, XLSX, Jupyter) | `doc-processing` |
| `doc_ingest_enhanced` | Extended ingestion with Unstructured/Docling | `doc-processing` |
| `section_sum` | Document section summarization | — |
| `sum_review` | Summary review and validation | — |
| `dependency_map` | Code dependency analysis | — |

### AI / LLM Providers

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `ollama_generate` | Local AI generation via Ollama | `ollama` |
| `openai_chat` | OpenAI chat completion | `openai` |
| `openai_completion` | OpenAI text completion | `openai` |
| `openai_embedding` | OpenAI embeddings | `openai` |
| `anthropic_chat` | Anthropic Claude chat | `anthropic` |
| `anthropic_completion` | Anthropic text completion | `anthropic` |
| `anthropic_embedding` | Anthropic embeddings | `anthropic` |
| `gemini_chat` | Google Gemini chat | `google-generativeai` |
| `gemini_completion` | Gemini text completion | `google-generativeai` |
| `gemini_embedding` | Gemini embeddings | `google-generativeai` |
| `mistral_chat` | Mistral AI chat | `mistralai` |
| `mistral_completion` | Mistral text completion | `mistralai` |
| `mistral_embedding` | Mistral embeddings | `mistralai` |
| `groq_chat` | Groq chat (fast inference) | `groq` |
| `groq_completion` | Groq text completion | `groq` |
| `groq_embedding` | Groq embeddings | `groq` |
| `huggingface_chat` | HuggingFace chat | `transformers` |
| `huggingface_completion` | HuggingFace text completion | `transformers` |
| `huggingface_embedding` | HuggingFace embeddings | `transformers` |
| `together_chat` | Together AI chat | `together` |
| `together_completion` | Together text completion | `together` |
| `together_embedding` | Together embeddings | `together` |
| `lm_studio_chat` | LM Studio local chat | `openai` |
| `lm_studio_completion` | LM Studio completion | `openai` |
| `lm_studio_embedding` | LM Studio embeddings | `openai` |

### Knowledge Graph & RAG

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `graphrag_init` | Initialize GraphRAG workspace | `advanced-rag` |
| `graphrag_index` | Build GraphRAG knowledge graph | `advanced-rag` |
| `graphrag_query` | Query GraphRAG index (local/global) | `advanced-rag` |
| `flexible_graphrag` | Flexible GraphRAG configuration | `advanced-rag` |
| `chromadb_store` | ChromaDB vector storage | `chromadb` |

### STEM & Scientific Computing

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `math_compute` | Mathematical expression evaluation | — |
| `cipher_ops` | Cryptographic operations | — |
| `physics_compute` | Astrophysics (Astropy: units, coordinates, cosmology) | `astropy` |
| `trefoil_simulation` | Knot theory: trefoil on Clifford torus with quaternions | `numpy` |
| `molecular_visualization` | 3D molecular coordinates (water, methane, benzene, caffeine) | — |
| `quantum_circuit_visualization` | 3D quantum circuit layout with gate geometries | — |
| `quantum_circuit` | Quantum circuit construction (Qiskit) | `qiskit` |
| `riscv_sim` | Pure-Python RV32I emulator with assembler | — |
| `riscv_cycle` | 5-stage RISC-V pipeline simulator (IF/ID/EX/MEM/WB) | — |
| `verilog_parse` | Verilog module parser (ports, signals, assigns) | — |
| `fpga_verify` | Verilog testbench generator with pseudo-random vectors | — |
| `myhdl_design` | MyHDL-to-Verilog transpiler | `myhdl` |
| `verilator_sim` | Verilator availability checker + lint | `verilator` (binary) |
| `data_viz_3d` | 3D mesh generation (sphere, torus, etc.) | — |
| `scipy_opt` | SciPy optimization (minimize, root, linprog, eig) | `scipy` |
| `diff_eq_solve` | ODE/PDE solvers via SciPy | `scipy` |
| `chem_analysis` | Molecular analysis with RDKit | `rdkit` |
| `bio_compute` | Bioinformatics with Biopython | `biopython` |
| `relativity` | General relativity calculations (SymPy/EinsteinPy) | `sympy` |

### Computer Vision

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `opencv_process` | OpenCV image processing | `opencv-python` |
| `yolo_detect` | YOLO object detection | `ultralytics` |

### ML & Data

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `optuna_tune` | Hyperparameter tuning with Optuna | `optuna` |

### Hardware & Maker

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `micropython` | MicroPython firmware utilities | `esptool` |
| `platformio` | PlatformIO project builder | `platformio` |

### UOR Ecosystem

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `uor_addr_canonicalize` | Canonicalize data per UOR-ADDR-1 + SHA-256 | — |
| `uor_addr_resolve` | Resolve UOR digest from integrator cache | — |
| `hologram_query` | Submit geometric inference to gethologram.ai | `httpx` |
| `hologram_status` | Check gethologram.ai service health | `httpx` |
| `moltbook_list` | List topics from moltbook.com/m/uor | `httpx` |
| `moltbook_search` | Search moltbook forum posts | `httpx` |
| `moltbook_post` | Post to moltbook forum | `httpx` |
| `prism_btc_anchor` | Anchor UOR digest on Bitcoin (placeholder) | — |
| `prism_btc_verify` | Verify Bitcoin anchor (placeholder) | — |
| `severance_infer` | Run inference via Severance AI (placeholder) | — |
| `severance_verify` | Verify Severance output (placeholder) | — |
| `anunix_health` | Check Anunix host health (placeholder) | — |
| `anunix_run` | Run command on Anunix (placeholder) | — |
| `uor_ecosystem_status` | Check all UOR ecosystem integrations | `httpx` |

### Autonomi (Decentralized Storage)

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `autonomi_upload` | Upload files to Autonomi (experimental) | `autonomi` |
| `autonomi_download` | Download files from Autonomi (experimental) | `autonomi` |
| `autonomi_status` | Check Autonomi connectivity and wallet | `autonomi` |

### Formal Language (ALM)

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `alm_analyze` | Analyze grammar specifications (BNF, EBNF) | — |
| `alm_generate` | Generate token sequences from prefix | — |
| `alm_verify` | Validate text against ALM grammar | — |

### Stub / Placeholder Skills

These skills are registered but currently return dependency-check status. They
become fully functional when the required package is installed:

| Skill | Required Package |
|-------|------------------|
| `agent_workflow` | `autogen` |
| `crewai_task`, `crewai_workflow` | `crewai` |
| `llamaindex_rag`, `llamaindex_query` | `llama-index` |
| `dagster_pipeline`, `dagster_status` | `dagster` |
| `mlflow_track`, `mlflow_deploy`, `model_reg` | `mlflow` |
| `kubeflow_pipe` | `kfp` |
| `airflow_dag` | `apache-airflow` |
| `dbt_transform` | `dbt-core` |
| `snowflake_etl` | `snowflake-connector-python` |
| `spark_process` | `pyspark` |
| `pentest_scan` | `python-nmap` |
| `osint_recon` | `shodan` |
| `crypto_analyze` | `pycryptodome` |
| `security_audit` | `bandit` |
| `face_recognize` | `face-recognition` |
| `video_analyze` | `moviepy` |
| `solana_tx` | `solana` |
| `smart_contract` | `web3` |
| `nft_mint` | `web3` |
| `autogluon_ml` | `autogluon` |
| `pycaret_ml` | `pycaret` |
| `flaml_auto` | `flaml` |
| `quantum_ml` | `pennylane` |
| `cern_root` | `uproot` |

### Optional Skill Dependencies

If optional extras are not installed, you will see harmless log warnings on
startup. The skill will become available once you install the relevant extras:

| Extra Group | Skills | Install Command |
|-------------|--------|-----------------|
| `doc-processing` | `doc_ingest`, `doc_ingest_enhanced` | `pip install -e ".[doc-processing]"` |
| `advanced-rag` | `graphrag_index`, `graphrag_query`, `flexible_graphrag` | `pip install -e ".[advanced-rag]"` |
| `autonomi` | `autonomi_upload`, `autonomi_download`, `autonomi_status` | `pip install -e ".[autonomi]"` |
| `agent-orchestration` | `agent_workflow`, `crewai_task`, `crewai_workflow` | `pip install -e ".[agent-orchestration]"` |
| `advanced` | All optional integrations | `pip install -e ".[advanced]"` |

## Development

```bash
# Run tests
pytest

# Lint and type check
ruff check .
mypy .

# Build web interface
cd apps/web && npm run build
```

## Architecture

```
Client (React / curl / CLI)
    │
    ▼
FastAPI Layer — /api/uar/run, /api/uar/stream, /api/health, /api/metrics
    │
    ▼
Middleware — CORS → Rate Limit → Auth → Logging → Body Parsing
    │
    ▼
Core Runtime — Planner → Executor → Skill Registry
    │
    ▼
Skills — Sequential / Parallel / Retry / Cache / Guardrails
    │
    ▼
Persistence — JSONL Store + Audit Logger + Redis (optional)
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design, data models, request flows, and deployment diagrams.

## Docker

```bash
# Production stack with Redis and Nginx
docker-compose -f docker-compose.prod.yml up --build
```

## Documentation

| Doc | Purpose |
|-----|---------|
| [Getting Started](docs/GETTING_STARTED.md) | API examples, curl commands, environment variables |
| [Architecture](docs/ARCHITECTURE.md) | Component map, data flow, deployment diagrams |
| [Onboarding](ONBOARDING.md) | Zero-to-running guide with Ollama + Web UI |
| [System Guide](SYSTEM.md) | Internal development, versioning, release process |
| [SLA](docs/SLA.md) | Service objectives, monitoring gaps, SLO targets |
| [Boot & Shutdown](docs/BOOT_AND_SHUTDOWN.md) | Startup/shutdown sequences per deployment mode |
| [WebSocket Protocol](docs/WEBSOCKET_PROTOCOL.md) | Event schema, streaming semantics |
| [API Reference](http://127.0.0.1:8000/docs) | Interactive OpenAPI docs (when running) |

## License

See LICENSE file.