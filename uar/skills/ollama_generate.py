import os
import logging

import httpx

from uar.core.registry import register_skill
from uar.core.circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

_ollama_cb = CircuitBreaker("ollama", failure_threshold=3, recovery_timeout=30.0)

# Limit on how much document context we send to the model (chars).
# Defaults to ~12k chars (~3k tokens) — safe for most local models.
MAX_DOC_CONTEXT_CHARS = int(os.getenv("OLLAMA_DOC_CONTEXT_CHARS", "12000"))
PER_DOC_CHAR_LIMIT = int(os.getenv("OLLAMA_PER_DOC_CHARS", "3000"))


def _gather_documents(ctx) -> list:
    """Pull documents from prior skills (e.g. doc_ingest) via PipelineContext.

    Looks for a 'doc_ingest' entry first, then any context entry with a
    'documents' list.
    """
    data = getattr(ctx, "data", None) or {}
    docs = []
    di = data.get("doc_ingest")
    if isinstance(di, dict) and isinstance(di.get("documents"), list):
        docs = di["documents"]
    else:
        for v in data.values():
            if isinstance(v, dict) and isinstance(v.get("documents"), list):
                docs = v["documents"]
                break
    return docs


def _build_context_block(docs: list) -> str:
    """Format documents into a model-friendly context block, truncated to limits."""
    if not docs:
        return ""
    parts: list[str] = []
    used = 0
    for d in docs:
        if not isinstance(d, dict):
            continue
        if d.get("error"):
            continue
        text = (d.get("text") or "").strip()
        if not text:
            continue
        path = d.get("path", "(unknown)")
        snippet = text[:PER_DOC_CHAR_LIMIT]
        block = f"\n--- FILE: {path} ---\n{snippet}\n"
        if used + len(block) > MAX_DOC_CONTEXT_CHARS:
            parts.append(f"\n[... {len(docs) - len(parts)} more files truncated ...]\n")
            break
        parts.append(block)
        used += len(block)
    return "".join(parts)


@register_skill("ollama_generate")
def ollama_generate(ctx):
    """Generate a local model response through Ollama.

    Reads documents from prior pipeline skills (e.g. doc_ingest) and includes
    them as context in the prompt so the model can review/summarize them.

    Environment:
      OLLAMA_HOST              (default: http://127.0.0.1:11434)
      OLLAMA_MODEL             (default: llama3.2:3b)
      OLLAMA_TIMEOUT_SECONDS   (default: 60)
      OLLAMA_DOC_CONTEXT_CHARS (default: 12000)
      OLLAMA_PER_DOC_CHARS     (default: 3000)

    Goal metadata overrides:
      ollama_prompt    — full prompt override (skips doc context)
      ollama_system    — optional system message prepended
      ollama_model     — model name override
    """
    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = ctx.goal.metadata.get("ollama_model") or os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
    system = ctx.goal.metadata.get("ollama_system")

    # Build prompt. Explicit override wins.
    explicit = ctx.goal.metadata.get("ollama_prompt")
    if explicit:
        prompt = explicit
        used_docs = 0
        context_chars = 0
    else:
        docs = _gather_documents(ctx)
        used_docs = sum(1 for d in docs if isinstance(d, dict) and not d.get("error") and d.get("text"))
        context = _build_context_block(docs)
        context_chars = len(context)
        objective = ctx.goal.objective or "Review the provided documents."
        if context:
            prompt = (
                f"{objective}\n\n"
                f"Use the following file contents as your sole source of truth.\n"
                f"{context}\n"
                f"Now respond to the goal above based on these files."
            )
        else:
            prompt = objective

    payload = {"model": model, "prompt": prompt, "stream": False}
    if system:
        payload["system"] = system

    try:
        response = _ollama_cb.call(lambda: httpx.post(f"{host.rstrip('/')}/api/generate", json=payload, timeout=timeout))
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        logger.warning(f"ollama_generate request failed: {exc}")
        return {
            "status": "failed",
            "model": model,
            "host": host,
            "error": str(exc),
            "documents_used": used_docs,
            "context_chars": context_chars,
        }

    return {
        "status": "completed",
        "model": model,
        "host": host,
        "response": data.get("response", ""),
        "documents_used": used_docs,
        "context_chars": context_chars,
        "raw": data,
    }
