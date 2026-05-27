"""GraphRAG integration skills.

Provides three skills:
  - graphrag_init   : bootstrap a GraphRAG workspace under
    <PROJECT_ROOT>/.uar_graphrag
  - graphrag_index  : run `graphrag index` over a source directory
    (default: library)
  - graphrag_query  : run `graphrag query --method=local|global`
    against the index

All three use the Ollama OpenAI-compatible endpoint so the pipeline
stays local.
Configure via env:
  OLLAMA_HOST               (default http://127.0.0.1:11434)
  OLLAMA_MODEL              (default llama3.2:3b)     - chat model
  OLLAMA_EMBED_MODEL        (default nomic-embed-text) - embedding model
  UAR_GRAPHRAG_ROOT         override workspace dir
"""

from __future__ import annotations

import os
import shutil
import subprocess
import logging
from pathlib import Path
from urllib.parse import urljoin

from uar.core.registry import register_skill
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.validation import validate_path_security

logger = logging.getLogger(__name__)

# Constants
DEFAULT_FAILURE_THRESHOLD = 3
DEFAULT_RECOVERY_TIMEOUT = 60.0  # seconds
DEFAULT_MAX_NODES = 10000
DEFAULT_CLI_TIMEOUT = 3600  # seconds (1 hour)
DEFAULT_QUERY_TIMEOUT = 600  # seconds (10 minutes)
REDUCE_MAX_TOKENS = 1000

# Resolve allowed root from environment with fallback to cwd
_allowed_root_env = os.getenv("PROJECT_ROOT")
ALLOWED_ROOT = (
    Path(_allowed_root_env).resolve() if _allowed_root_env else Path.cwd()
)

_graphrag_cb = CircuitBreaker(
    "graphrag",
    failure_threshold=DEFAULT_FAILURE_THRESHOLD,
    recovery_timeout=DEFAULT_RECOVERY_TIMEOUT,
)

# Graph size limits to prevent unbounded growth
MAX_NODES = max(
    1,
    int(
        os.getenv("GRAPHRAG_MAX_NODES", str(DEFAULT_MAX_NODES)).strip()
        or str(DEFAULT_MAX_NODES)
    ),
)
MAX_EDGES = max(
    1,
    int(os.getenv("GRAPHRAG_MAX_EDGES", "50000").strip() or "50000"),
)
MAX_ENTITY_LIMIT = max(
    1,
    int(os.getenv("GRAPHRAG_MAX_ENTITY_LIMIT", "5000").strip() or "5000"),
)

# Schema versioning for graph data
GRAPH_SCHEMA_VERSION = "v1"  # Current graph schema version


def _check_graph_size_limits(root: Path) -> tuple[bool, str]:
    """Check if existing graph exceeds size limits.

    Returns (within_limits, error_message).
    """
    entities_path = root / "output" / "create_final_entities.parquet"
    relationships_path = root / "output" / "create_final_relationships.parquet"

    if not entities_path.exists() or not relationships_path.exists():
        return True, ""  # No graph yet, within limits

    try:
        import pandas as pd

        # Count entities (nodes)
        entities_df = pd.read_parquet(entities_path)
        entity_count = len(entities_df)

        # Count relationships (edges)
        relationships_df = pd.read_parquet(relationships_path)
        edge_count = len(relationships_df)

        if entity_count > MAX_NODES:
            return (
                False,
                f"Graph exceeds node limit ({entity_count} > {MAX_NODES})",
            )

        if edge_count > MAX_EDGES:
            return (
                False,
                f"Graph exceeds edge limit ({edge_count} > {MAX_EDGES})",
            )

        return True, ""
    except Exception as e:
        logger.warning(f"Failed to check graph size limits: {e}")
        return True, ""  # Allow continuation if check fails


def _get_graph_schema_version(root: Path) -> str:
    """Get the schema version of an existing graph.

    Returns the schema version string (e.g., "v1") or "unknown" if not found.
    """
    version_file = root / "schema_version.txt"
    if version_file.exists():
        return version_file.read_text().strip()
    return "unknown"


def _set_graph_schema_version(
    root: Path, version: str = GRAPH_SCHEMA_VERSION
) -> None:
    """Set the schema version for a graph."""
    version_file = root / "schema_version.txt"
    version_file.write_text(version, encoding="utf-8")


def _check_schema_compatibility(root: Path) -> tuple[bool, str]:
    """Check if existing graph schema is compatible with current version.

    Returns (is_compatible, error_message).
    """
    current_version = _get_graph_schema_version(root)
    if current_version == "unknown":
        # No version file, assume compatible for new graphs
        return True, ""

    if current_version != GRAPH_SCHEMA_VERSION:
        return (
            False,
            f"Graph schema version mismatch: "
            f"existing={current_version}, current={GRAPH_SCHEMA_VERSION}. "
            "Run graphrag_init to reset.",
        )

    return True, ""


def _check_ollama_health() -> tuple[bool, str]:
    """Check if Ollama is reachable. Returns (is_healthy, error_message)."""
    import httpx

    try:
        ollama_host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
        r = httpx.get(urljoin(ollama_host, "/api/tags"), timeout=5.0)
        if r.is_success:
            return True, ""
        return False, f"Ollama returned HTTP {r.status_code}"
    except Exception as e:
        return False, f"Ollama unreachable: {e}"


SETTINGS_YAML = """\
encoding_model: cl100k_base
skip_workflows: []

models:
  default_chat_model:
    type: openai_chat
    api_base: {ollama_host}/v1
    api_key: ollama
    model: {chat_model}
    model_supports_json: false
    max_tokens: 2000
    request_timeout: 180.0
    tokens_per_minute: 50000
    requests_per_minute: 60
    max_retries: 3
    concurrent_requests: 2
    async_mode: threaded
  default_embedding_model:
    type: openai_embedding
    api_base: {ollama_host}/v1
    api_key: ollama
    model: {embed_model}
    batch_size: 16
    tokens_per_minute: 200000
    requests_per_minute: 120
    max_retries: 3
    concurrent_requests: 2
    async_mode: threaded

input:
  type: file
  file_type: text
  base_dir: "input"
  file_encoding: utf-8
  file_pattern: ".*\\\\.txt$"

chunks:
  size: 800
  overlap: 120
  group_by_columns: [id]

cache:
  type: file
  base_dir: "cache"

storage:
  type: file
  base_dir: "output"

reporting:
  type: file
  base_dir: "logs"

entity_extraction:
  model_id: default_chat_model
  max_gleanings: 1

summarize_descriptions:
  model_id: default_chat_model
  max_length: 500

community_reports:
  model_id: default_chat_model
  max_length: 1500
  max_input_length: 4000

claim_extraction:
  enabled: false
  model_id: default_chat_model

embed_text:
  model_id: default_embedding_model

cluster_graph:
  max_cluster_size: 10

umap:
  enabled: false

snapshots:
  graphml: true
  embeddings: false
  transient: false

local_search:
  chat_model_id: default_chat_model
  embedding_model_id: default_embedding_model
  text_unit_prop: 0.5
  community_prop: 0.1
  top_k_mapped_entities: 10
  top_k_relationships: 10
  max_tokens: 8000

global_search:
  chat_model_id: default_chat_model
  max_tokens: 8000
  data_max_tokens: 8000
  map_max_tokens: 500
  reduce_max_tokens: REDUCE_MAX_TOKENS
  concurrency: 2
"""


def _project_root() -> Path:
    """Get the project root, using the pre-validated ALLOWED_ROOT."""
    return ALLOWED_ROOT


def _graphrag_root() -> Path:
    custom = os.getenv("UAR_GRAPHRAG_ROOT")
    if custom:
        return Path(custom).resolve()
    return _project_root() / ".uar_graphrag"


def _write_settings(root: Path) -> Path:
    """Write settings.yaml into the workspace, overwriting each time."""
    settings_path = root / "settings.yaml"
    content = SETTINGS_YAML.format(
        ollama_host=os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip(
            "/"
        ),
        chat_model=os.getenv("OLLAMA_MODEL", "llama3.2:3b"),
        embed_model=os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text"),
    )
    settings_path.write_text(content, encoding="utf-8")
    return settings_path


def _ensure_workspace() -> Path:
    root = _graphrag_root()
    (root / "input").mkdir(parents=True, exist_ok=True)
    (root / "output").mkdir(parents=True, exist_ok=True)
    (root / "cache").mkdir(parents=True, exist_ok=True)
    (root / "logs").mkdir(parents=True, exist_ok=True)
    (root / "prompts").mkdir(parents=True, exist_ok=True)
    _write_settings(root)
    # Minimal .env to satisfy graphrag's API key lookup
    env_file = root / ".env"
    if not env_file.exists():
        # Use environment variable for API key if set,
        # otherwise use placeholder
        api_key = os.getenv("GRAPHRAG_API_KEY", "ollama")
        env_file.write_text(f"GRAPHRAG_API_KEY={api_key}\n", encoding="utf-8")
    return root


def _stage_inputs(source_dir: Path, input_dir: Path) -> int:
    """Stage readable documents from source into graphrag input/ as .txt.

    Reuses doc_ingest's extractors so PDFs/DOCX/XLSX/IPYNB/Parquet are handled.
    Returns count of staged files.
    """
    from uar.skills.doc_ingest import _read_file_safely, ALLOWED_EXTENSIONS

    # Wipe existing input dir to avoid stale files
    if input_dir.exists():
        shutil.rmtree(input_dir)
    input_dir.mkdir(parents=True, exist_ok=True)

    staged = 0
    paths = (
        [source_dir] if source_dir.is_file() else list(source_dir.rglob("*"))
    )
    for p in paths:
        if not p.is_file():
            continue
        if p.suffix.lower() not in ALLOWED_EXTENSIONS:
            continue
        doc = _read_file_safely(
            p, source_dir if source_dir.is_dir() else source_dir.parent
        )
        text = (doc.get("text") or "").strip()
        if not text or doc.get("error"):
            continue
        # Flatten nested paths to filename-based identifiers
        rel = doc.get("path") or p.name
        safe = rel.replace("/", "_").replace("\\", "_")
        out = input_dir / (safe + ".txt")
        out.write_text(text, encoding="utf-8")
        staged += 1
    return staged


def _run_cli(
    args: list[str], cwd: Path, timeout: int = DEFAULT_CLI_TIMEOUT
) -> dict:
    """Run graphrag CLI. Returns {returncode, stdout, stderr}."""
    return _graphrag_cb.call(_run_cli_impl, args, cwd, timeout)


def _run_cli_impl(
    args: list[str], cwd: Path, timeout: int = DEFAULT_CLI_TIMEOUT
) -> dict:
    """Internal implementation of graphrag CLI runner."""
    try:
        proc = subprocess.run(
            args,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout[-20000:],
            "stderr": proc.stderr[-20000:],
        }
    except subprocess.TimeoutExpired as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"timeout after {timeout}s: {e}",
        }
    except FileNotFoundError as e:
        return {
            "returncode": -1,
            "stdout": "",
            "stderr": f"graphrag CLI not found: {e}",
        }


@register_skill("graphrag_init")
def graphrag_init(ctx):
    """Create or refresh the GraphRAG workspace at
    <PROJECT_ROOT>/.uar_graphrag."""
    root = _ensure_workspace()
    _set_graph_schema_version(root)  # Set current schema version
    return {
        "status": "completed",
        "workspace": str(root),
        "settings": str(root / "settings.yaml"),
        "schema_version": GRAPH_SCHEMA_VERSION,
    }


@register_skill("graphrag_index")
def graphrag_index(ctx):
    """Stage documents and build the GraphRAG knowledge graph.

    Metadata:
      input_path   : file or directory to index (default: library)
      timeout_sec  : max CLI run time (default 3600)
    """
    # Pre-flight check: ensure Ollama is reachable
    is_healthy, error_msg = _check_ollama_health()
    if not is_healthy:
        return {
            "status": "failed",
            "error": (
                f"Ollama health check failed: {error_msg}. "
                "Ensure Ollama is running."
            ),
        }

    root = _ensure_workspace()
    meta = ctx.goal.metadata or {}
    src = meta.get("input_path") or str(_project_root() / ".uar_library")
    source = Path(src).resolve()

    # Validate path security
    try:
        validate_path_security(source, ALLOWED_ROOT)
    except Exception as e:
        return {"status": "failed", "error": f"Path security violation: {e}"}

    if not source.exists():
        return {
            "status": "failed",
            "error": f"input_path does not exist: {source}",
        }

    # Check graph size limits before indexing
    within_limits, limit_error = _check_graph_size_limits(root)
    if not within_limits:
        return {
            "status": "failed",
            "error": (
                f"Graph size limit exceeded: {limit_error}. "
                "Consider clearing the workspace with graphrag_init."
            ),
        }

    # Check schema compatibility before indexing
    compatible, schema_error = _check_schema_compatibility(root)
    if not compatible:
        return {
            "status": "failed",
            "error": schema_error,
        }

    staged = _stage_inputs(source, root / "input")
    if staged == 0:
        return {
            "status": "failed",
            "error": "No ingestible files found in input_path",
            "input_path": str(source),
        }

    timeout = max(1, min(int(meta.get("timeout_sec") or DEFAULT_CLI_TIMEOUT), 7200))
    result = _run_cli(
        ["graphrag", "index", "--root", str(root)],
        cwd=root,
        timeout=timeout,
    )
    return {
        "status": "completed" if result["returncode"] == 0 else "failed",
        "workspace": str(root),
        "files_staged": staged,
        "returncode": result["returncode"],
        "stdout_tail": result["stdout"][-4000:],
        "stderr_tail": result["stderr"][-4000:],
    }


@register_skill("graphrag_query")
def graphrag_query(ctx):
    """Query the existing GraphRAG index.

    Metadata:
      graphrag_method : "local" (default) or "global"
      graphrag_query  : query string (falls back to goal.objective)
      timeout_sec     : default 600
    """
    root = _graphrag_root()
    settings = root / "settings.yaml"
    if not settings.exists():
        return {
            "status": "failed",
            "error": (
                f"No GraphRAG workspace at {root}. Run graphrag_index first."
            ),
        }

    # Check graph size limits before querying
    within_limits, limit_error = _check_graph_size_limits(root)
    if not within_limits:
        return {
            "status": "failed",
            "error": (
                f"Graph size limit exceeded: {limit_error}. "
                "Consider clearing the workspace with graphrag_init."
            ),
        }

    # Check schema compatibility before querying
    compatible, schema_error = _check_schema_compatibility(root)
    if not compatible:
        return {
            "status": "failed",
            "error": schema_error,
        }

    meta = ctx.goal.metadata or {}
    method = (meta.get("graphrag_method") or "local").lower()
    if method not in ("local", "global"):
        method = "local"
    query = meta.get("graphrag_query") or ctx.goal.objective or ""
    if not query.strip():
        return {"status": "failed", "error": "Empty query"}

    timeout = max(
        1, min(
            int(meta.get("timeout_sec") or DEFAULT_QUERY_TIMEOUT), 7200
        )
    )
    result = _run_cli(
        [
            "graphrag",
            "query",
            "--root",
            str(root),
            "--method",
            method,
            "--query",
            query,
        ],
        cwd=root,
        timeout=timeout,
    )
    # graphrag prints its answer on stdout; extract the response block
    response = result["stdout"]
    # Trim any "SUCCESS:" preamble graphrag emits
    if "SUCCESS:" in response:
        response = response.split("SUCCESS:", 1)[1].strip()
    return {
        "status": "completed" if result["returncode"] == 0 else "failed",
        "method": method,
        "query": query,
        "response": response,
        "returncode": result["returncode"],
        "stderr_tail": result["stderr"][-2000:],
    }
