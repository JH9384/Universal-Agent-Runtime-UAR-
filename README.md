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
- `graphrag_skills`: Graph-based retrieval augmentation

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