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

- `section_sum`: Document section summarization
- `doc_ingest`: Multi-format document ingestion
- `dependency_map`: Code dependency analysis
- `sum_review`: Summary review and validation
- `ollama_generate`: Local AI generation via Ollama
- `graphrag_init`: Initialize GraphRAG workspace
- `graphrag_index`: Build GraphRAG knowledge graph
- `graphrag_query`: Query GraphRAG index (local/global methods)
- `autonomi_upload`: Upload files to Autonomi decentralized storage (experimental)
- `autonomi_download`: Download files from Autonomi (experimental)
- `autonomi_status`: Check Autonomi connectivity and wallet status (experimental)
- `alm_analyze`: Analyze formal grammar specifications (BNF, EBNF)
- `alm_generate`: Generate token sequences from a prefix
- `alm_verify`: Validate text against ALM grammar
- `uor_addr_canonicalize`: Canonicalize data per UOR-ADDR-1 and compute SHA-256 digest
- `uor_addr_resolve`: Resolve a UOR digest from the integrator cache
- `uor_foundation_verify`: Call the live UOR Foundation API (`api.uor.foundation/v1`)
- `hologram_query`: Submit geometric inference to gethologram.ai
- `hologram_status`: Check gethologram.ai service health
- `moltbook_list`: List recent topics from moltbook.com/m/uor forum
- `moltbook_search`: Search moltbook.com/m/uor forum posts
- `moltbook_post`: Post a new topic to the moltbook forum
- `prism_btc_anchor`: Anchor a UOR digest on Bitcoin (placeholder)
- `severance_infer`: Run inference via Severance AI (placeholder)
- `anunix_health`: Check Anunix host health (placeholder)
- `uor_ecosystem_status`: Check status of all UOR ecosystem integrations

### Optional Skill Dependencies

Some skills require optional packages that are not included in the base
installation. If those extras are not installed, you will see harmless
log warnings on startup such as:

```
Recipe 'review' references unregistered skill: doc_ingest
Recipe 'gr_index' references unregistered skill: graphrag_index
```

These warnings mean the skill module is loaded but its underlying
libraries are missing. The skill will become available once you install
the relevant extras:

| Skill(s) | Extra group | Install command |
|---|---|---|
| `doc_ingest` | `doc-processing` | `pip install -e ".[doc-processing]"` |
| `graphrag_index`, `graphrag_query` | `advanced-rag` | `pip install -e ".[advanced-rag]"` |
| `autonomi_upload`, `autonomi_download` | `autonomi` | `pip install -e ".[autonomi]"` |

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

## Documentation

- [System Guide](SYSTEM.md)
- [Getting Started](docs/GETTING_STARTED.md)
- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](http://127.0.0.1:8000/docs) (when running)

## License

See LICENSE file.