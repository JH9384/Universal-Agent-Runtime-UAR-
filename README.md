# Universal Agent Runtime (UAR) v1.0.0

UOR-aligned agent execution layer for modular goal-driven agent workflows.

## Features

- **Modular Runtime**: Extensible skill-based execution engine
- **Event Streaming**: Real-time execution monitoring via Server-Sent Events
- **Document Processing**: Multi-format ingestion (PDF, DOCX, XLSX, Jupyter, etc.)
- **API Server**: Production-ready FastAPI server with security middleware
- **Web Interface**: React-based control surface for workflow visualization
- **Replay & Persistence**: JSONL-based run storage with event reconstruction
- **Security**: Path validation, rate limiting, input sanitization

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

```bash
# Clone repository
git clone https://github.com/JH9384/Universal-Agent-Runtime-UAR-.git
cd Universal-Agent-Runtime-UAR-

# Install Python dependencies
pip install -e .

# Install web dependencies (optional)
cd apps/web
npm install
npm run build
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