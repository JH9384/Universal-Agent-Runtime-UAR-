# Universal Agent Runtime (UAR) v1.1.0

Modular execution platform for reproducible agent workflows and scientific computing.

UAR is both an **agent runtime** (goal-driven, event-streamed, observable) and a **browser-accessible scientific computing sandbox** (quantum circuits, molecular dynamics, RISC-V emulation, Verilog simulation). You don't install toolchains. You send JSON goals and get structured results.

## Features

### Execution Engine
- **Modular Runtime**: 124+ skill-based execution engine with circuit breaker protection
- **Event Streaming**: Real-time execution monitoring via Server-Sent Events and WebSocket
- **Hierarchical Execution**: Recipes as discrete nested units with snapshot/retry/params scoping (opt-in via `UAR_HIERARCHICAL_EXECUTION=true`)
- **Recipe-Level Caching**: Context mutations cached per recipe ID and parameters
- **Replay & Persistence**: JSONL-based run storage with event reconstruction for full audit trails

### Scientific Computing
- **Quantum**: 3D circuit layout with gate geometries, entanglement visualization, Qiskit integration
- **Molecular**: 3D atomic coordinates (water→caffeine), bond topology, protein backbone generation
- **Physics**: Astropy cosmology (Planck18), coordinate transforms, unit conversions with circuit breaker
- **Hardware**: RV32I emulator with assembler, 5-stage RISC-V pipeline, Verilog parser, FPGA testbench generator
- **Embedded**: MicroPython GPIO simulation, PlatformIO project generation
- **Math**: Quaternion trefoil knots on Clifford torus, ODE/PDE solvers, optimization, relativity tensors

### AI & Integration
- **Document Processing**: Multi-format ingestion (PDF, DOCX, XLSX, Jupyter, etc.)
- **API Server**: Production-ready FastAPI server with security middleware
- **Web Interface**: React-based control surface for workflow visualization
- **UOR Ecosystem Integration**: Live API clients for UOR Foundation, Hologram, Moltbook, and more
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

### UOR alignment snapshot

UAR pins the upstream **UOR-Foundation/UOR-Framework** release under
`third_party/uor`. We currently align to **v0.5.2** (released 2026-05-23) and
record SHA-256 digests for all ontology/shape artifacts so schema validation is
reproducible.

Refresh the pinned assets with:

```bash
python scripts/fetch_uor_artifacts.py --tag v0.5.2
```

The script downloads into `third_party/uor/cache/<tag>/` and verifies against
[`DIGESTS.json`](third_party/uor/DIGESTS.json). When the UOR Foundation publishes
a new release:

1. Update `third_party/uor/VERSION` and the digests file.
2. Re-run the fetch script.
3. Run `python scripts/validate_uor_alignment.py` (SHACL + JSON Schema) before
   advertising the new alignment level.

### Run Locally

```bash
# Start API server
python -m uvicorn uar.api.server:app --host 127.0.0.1 --port 8000

# Open API docs
open http://127.0.0.1:8000/docs

# Start web interface
cd apps/web && npm run dev
```

### Basic Usage — Agent Workflow

```python
from uar.core.contracts import GoalSpec
from uar.core.planner import SimplePlanner
from uar.core.executor import Executor

# Document summarization
goal = GoalSpec(
    id="doc-1",
    user_intent="Summarize README",
    objective="Produce a 3-bullet summary",
    metadata={"input_path": "docs/README.md"},
)
planner = SimplePlanner()
strategy = planner.plan(goal)
result = Executor().run(strategy, goal)
```

### Basic Usage — Scientific Computing

```python
# Molecular visualization — no RDKit, no Jupyter needed
from uar.skills.molecular_visualization import molecular_visualization
from uar.core.contracts import PipelineContext, GoalSpec

ctx = PipelineContext(
    goal=GoalSpec(
        id="mol-1",
        user_intent="Visualize caffeine",
        objective="Return 3D coordinates",
        metadata={"molecule": "caffeine"},
    )
)
result = molecular_visualization(ctx)
# result["result"]["atoms"] → list of {element, x, y, z, radius, color}
# result["result"]["bonds"] → list of (atom_i, atom_j, distance)
```

## Available Skills

**127 skill names registered** across 15 categories (117 unique implementations
plus 10 aliases). All skills have full implementations; optional-dependency
skills gracefully return a dependency-check response when their required package
is not installed.

### Document Processing

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `doc_ingest` | Multi-format document ingestion (PDF, DOCX, XLSX, Jupyter) | `doc-processing` |
| `doc_ingest_enhanced` | Extended ingestion with Unstructured/Docling | `doc-processing` |
| `section_sum` | Document section summarization | — |
| `sum_review` | Summary review and validation | — |
| `dependency_map` | Code dependency analysis | — |
| `code_analysis` | Multi-language static analysis (Python, JS, Go, Rust, etc.) | — |

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
| `llamaindex_rag` | LlamaIndex RAG indexing and querying | `llama-index` |
| `llamaindex_query` | LlamaIndex standalone query | `llama-index` |

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
| `math_plot` | 2D mathematical plotting (functions, parametric, polar) | `matplotlib` |
| `math_plot_3d` | 3D surface, wireframe, and parametric plots | `matplotlib` |
| `crypto_analyze` | Cryptographic analysis: hash ID, entropy, key strength | `pycryptodome` |
| `quantum_ml` | Quantum neural networks, VQE, QAOA (PennyLane) | `pennylane` |
| `cern_root` | Read CERN ROOT files and extract TTree data | `uproot` |

### Computer Vision

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `opencv_process` | OpenCV image processing | `opencv-python` |
| `yolo_detect` | YOLO object detection | `ultralytics` |
| `face_recognize` | Face recognition and comparison | `face-recognition` |
| `video_analyze` | Frame extraction, motion detection, histogram | `opencv-python` |

### ML & Data

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `optuna_tune` | Hyperparameter tuning with Optuna | `optuna` |
| `chromadb_store` | ChromaDB vector storage operations | `chromadb` |
| `flaml_auto` | Automated ML with FLAML | `flaml` |
| `pycaret_ml` | Automated ML pipeline with PyCaret | `pycaret` |
| `autogluon_ml` | Automated ML with AutoGluon | `autogluon` |

### Data Engineering

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `airflow_dag` | Validate and inspect Airflow DAG files | `apache-airflow` |
| `dbt_transform` | Compile dbt project and list models | `dbt-core` |
| `snowflake_etl` | Execute queries via Snowflake connector | `snowflake-connector-python` |
| `spark_process` | Create Spark session, run SQL, return schema | `pyspark` |

### Security

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `security_audit` | Run bandit and safety audits | `bandit` |
| `pentest_scan` | Network penetration testing with python-nmap | `python-nmap` |
| `osint_recon` | WHOIS, DNS, and Shodan reconnaissance | `shodan`, `whois` |

### Blockchain

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `solana_tx` | Solana keypair, balance, test-transfer | `solana` |
| `smart_contract` | Deploy minimal contract via web3 (testnet only) | `web3` |
| `nft_mint` | Mint ERC-721 on local testnet | `web3` |

### Hardware & Maker

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `micropython` | MicroPython firmware utilities | `esptool` |
| `platformio` | PlatformIO project builder | `platformio` |

### MLOps & Pipelines

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `mlflow_track` | Log params, metrics, artifacts to MLflow | `mlflow` |
| `mlflow_deploy` | Load registered model from MLflow | `mlflow` |
| `model_reg` | Register and stage model in MLflow | `mlflow` |
| `kubeflow_pipe` | Compile KFP pipeline to YAML | `kfp` |
| `dagster_pipeline` | Dagster pipeline (requires `dagster`) | `dagster` |
| `dagster_status` | Dagster status check | `dagster` |

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
| `prism_btc_anchor` | Anchor UOR digest on Bitcoin (mock when unconfigured) | — |
| `prism_btc_verify` | Verify Bitcoin anchor (mock when unconfigured) | — |
| `severance_infer` | Run inference via Severance AI (falls back to local LLM) | — |
| `severance_verify` | Verify Severance output (local heuristic when unconfigured) | — |
| `anunix_health` | Check Anunix host health (local when unconfigured) | — |
| `anunix_run` | Run command on Anunix (sandboxed local when unconfigured) | — |
| `uor_ecosystem_status` | Check all UOR ecosystem integrations | `httpx` |
| `uor_foundation_verify` | Call live UOR Foundation API verify endpoint | `httpx` |

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

### Agent Orchestration

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `agent_workflow` | Multi-agent workflow execution | `autogen` |
| `crewai_task` | CrewAI single task execution | `crewai` |
| `crewai_workflow` | CrewAI multi-agent workflow | `crewai` |

### Governance & Multi-Agent

| Skill | Description | Dependencies |
|-------|-------------|--------------|
| `guardrail_check` | Validate input/output against guardrail rules | — |
| `blackboard_message` | Post or read messages on shared blackboard | — |
| `blackboard_status` | Read blackboard state and agent positions | — |
| `budget_status` | Check multi-agent budget and spending limits | — |

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

## Recipes

Recipes are **named bundles of skills** that run as a discrete unit with snapshot, retry, and parameter scoping. The frontend supports drag-and-drop reordering of mixed skills and recipes in a unified execution order.

### Canonical Recipes (10 built-in)

| Recipe | Label | Skills |
|--------|-------|--------|
| `review` | 🦙 Ollama review | `doc_ingest`, `ollama_generate` |
| `deps` | 🕸️ Dep map | `doc_ingest`, `dependency_map`, `sum_review` |
| `gr_index` | 📚 GraphRAG index | `graphrag_index` |
| `gr_query` | 🔎 GraphRAG query | `graphrag_query` |
| `gr_full` | ⚡ Full pipeline | `graphrag_index`, `graphrag_query` |
| `auto_up` | ☁️ Autonomi upload | `autonomi_upload` |
| `auto_down` | ☁️ Autonomi download | `autonomi_download` |
| `auto_status` | ☁️ Autonomi status | `autonomi_status` |
| `eco_status` | 🌐 Ecosystem status | `uor_ecosystem_status` |
| `eco_canon` | 🌐 Canonicalize | `uor_addr_canonicalize` |

Recipes can be **nested** (a recipe may reference another recipe) and users can create their own recipes via the web UI or API. User recipes are persisted to `.uar_data/user_recipes.json`.

## Metrics & Observability

Every run produces structured telemetry:

- **Per-skill timing**: count, avg duration, p50/p99 percentiles
- **Per-endpoint histograms**: Prometheus-compatible bucket counts
- **Event stream**: `recipe_start`, `skill_start`, `skill_complete`, `metrics` events via WebSocket
- **JSONL audit trail**: Every execution is recorded with full lineage for replay and forensics

### Endpoints

| Endpoint | Purpose |
|----------|---------|
| `/api/metrics` | Prometheus exposition format (histograms, counts, sums) |
| `/api/metrics/json` | JSON snapshot of all endpoint and skill stats |
| `/api/uar/stream/ws` | Live WebSocket event stream |
| `/api/uar/stream` | Server-Sent Events fallback |

### Example Metrics Output

```json
{
  "skills": {
    "molecular_visualization": {
      "count": 12,
      "avg_duration_ms": 4.5,
      "p50_ms": 3.2,
      "p99_ms": 18.7,
      "error_rate": 0.0
    }
  }
}
```

## Examples

Ready-to-run JSON payloads are in `examples/user_payloads/`:

| File | What it does |
|------|--------------|
| `codebase_graph.json` | Ingest repo → build dependency graph |
| `documentation_review.json` | Ingest docs → LLM review → summary |
| `graphrag_index.json` | Build a knowledge graph from documents |
| `math_solve.json` | Symbolic math computation |
| `physics_unit_convert.json` | Astropy unit conversion |
| `trefoil_simulation.json` | Quaternion trefoil knot on Clifford torus |
| `nested_recipe_timeline.json` | Mixed skills + recipes with event streaming |

Run any payload:

```bash
curl http://localhost:8000/api/uar/run \
  -H "Content-Type: application/json" \
  -d @examples/user_payloads/trefoil_simulation.json
```

See [docs/USER_EXAMPLES.md](docs/USER_EXAMPLES.md) for the full walkthrough.

## Security

UAR implements defense-in-depth at multiple layers:

- **Input validation**: Path traversal checks (null bytes, hex encoding, symlink detection, cross-device hard links)
- **Rate limiting**: Sliding-window rate limiter — atomic Lua script in Redis (multi-worker) or thread-safe deque (single-process)
- **Authentication**: API key middleware with tier-based rate limits; `/api/health/dashboard` requires auth
- **Async-safe connection counters**: WebSocket connection counter uses `async with self.lock` for race-free acquire/release
- **SSRF prevention**: URL scheme and host validation on external requests
- **Resource limits**: 100MB total file size cap, max file count limits in document ingestion
- **Secret management**: All secrets via environment variables (no hardcoded keys)
- **Zero npm CVEs**: `vite` 7.3.3 + `vitest` 3.2.4 (esbuild CORS CVE GHSA-67mh-4wv8-2f99 resolved)

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

```text
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
| [Recipe Conditions](docs/RECIPE_CONDITIONS.md) | Conditional recipe execution with `exists`/`equals`/`not_equals` operators |
| [Boot & Shutdown](docs/BOOT_AND_SHUTDOWN.md) | Startup/shutdown sequences per deployment mode |
| [WebSocket Protocol](docs/WEBSOCKET_PROTOCOL.md) | Event schema, heartbeat, batching, reconnect guide |
| [API Reference](http://127.0.0.1:8000/docs) | Interactive OpenAPI docs (when running) |

## License

See LICENSE file.