import os

import httpx

from uar.core.registry import register_skill


@register_skill("ollama_generate")
def ollama_generate(ctx):
    """Generate a local model response through Ollama.

    This skill is optional and requires a local Ollama server. It keeps UAR's
    runtime contract unchanged by reading input from PipelineContext and writing
    a normal skill output dictionary.
    """

    host = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))

    prompt = ctx.goal.objective
    if ctx.goal.metadata.get("ollama_prompt"):
        prompt = ctx.goal.metadata["ollama_prompt"]

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
    }

    try:
        response = httpx.post(f"{host.rstrip('/')}/api/generate", json=payload, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:
        return {
            "status": "failed",
            "model": model,
            "host": host,
            "error": str(exc),
        }

    return {
        "status": "completed",
        "model": model,
        "host": host,
        "response": data.get("response", ""),
        "raw": data,
    }
