"""UOR Ecosystem skills for UAR.

Exposes every UOR ecosystem integration as a registered skill so
recipes and execution pipelines can call them by name.

Skills:
  - uor_addr_canonicalize : canonicalize data per UOR-ADDR-1
  - uor_addr_resolve      : resolve a UOR digest from cache
  - hologram_query        : submit geometric inference to Hologram
  - hologram_status       : check Hologram service health
  - moltbook_list         : list recent moltbook forum topics
  - moltbook_search       : search moltbook forum posts
  - moltbook_post         : post a new topic to moltbook (needs key)
  - prism_btc_anchor      : anchor a digest on Bitcoin (placeholder)
  - prism_btc_verify      : verify an on-chain anchor (placeholder)
  - severance_infer       : run inference via Severance AI (placeholder)
  - severance_verify      : verify inference output (placeholder)
  - anunix_health         : check Anunix host health (placeholder)
  - anunix_run            : run command on Anunix host (placeholder)
  - uor_ecosystem_status  : overall ecosystem integration status
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.uor_ecosystem import get_uor_ecosystem

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# UOR-ADDR skills
# ---------------------------------------------------------------------------

@register_skill("uor_addr_canonicalize")
def uor_addr_canonicalize(ctx: PipelineContext) -> Dict[str, Any]:
    """Canonicalize data per UOR-ADDR-1 and return digest envelope.

    Metadata:
      data  — Python object to canonicalize (required)
    """
    meta = ctx.goal.metadata or {}
    data = meta.get("data")
    if data is None:
        return {"status": "failed", "error": "metadata 'data' required"}

    eco = get_uor_ecosystem()
    envelope = eco.uor_addr.canonicalize(data)
    uor_obj = eco.uor_addr.wrap_with_uor(data)
    return {
        "status": "completed",
        "envelope": envelope,
        "uor_digest": uor_obj.digest,
        "uor_size": uor_obj.size,
    }


@register_skill("uor_addr_resolve")
def uor_addr_resolve(ctx: PipelineContext) -> Dict[str, Any]:
    """Resolve a UOR digest from the integrator cache.

    Metadata:
      digest  — sha256:<hex> digest to look up (required)
    """
    meta = ctx.goal.metadata or {}
    digest = meta.get("digest", "")
    if not digest:
        return {"status": "failed", "error": "metadata 'digest' required"}

    eco = get_uor_ecosystem()
    obj = eco.uor_addr.resolve(digest)
    if obj is None:
        return {"status": "failed", "error": f"digest not found: {digest}"}

    return {
        "status": "completed",
        "digest": digest,
        "data": obj.data,
        "mediaType": obj.media_type,
        "provenance": obj.provenance,
    }


# ---------------------------------------------------------------------------
# Hologram skills
# ---------------------------------------------------------------------------

@register_skill("hologram_query")
def hologram_query(ctx: PipelineContext) -> Dict[str, Any]:
    """Submit a geometric inference query to gethologram.ai.

    Metadata:
      model_id  — Hologram model identifier (default "default")
      inputs    — dict of model inputs (default {})
    """
    meta = ctx.goal.metadata or {}
    model_id = meta.get("model_id", "default")
    inputs = meta.get("inputs", {})

    eco = get_uor_ecosystem()
    result = eco.hologram.query(model_id, inputs)
    return {"status": "completed", "model_id": model_id, **result}


@register_skill("hologram_status")
def hologram_status(ctx: PipelineContext) -> Dict[str, Any]:
    """Check Hologram service health."""
    eco = get_uor_ecosystem()
    result = eco.hologram.status()
    return {"status": "completed", **result}


# ---------------------------------------------------------------------------
# Moltbook skills
# ---------------------------------------------------------------------------

@register_skill("moltbook_list")
def moltbook_list(ctx: PipelineContext) -> Dict[str, Any]:
    """List recent topics from moltbook.com/m/uor.

    Metadata:
      category  — forum category (default "uor")
      limit     — max topics to return (default 10)
    """
    meta = ctx.goal.metadata or {}
    category = meta.get("category", "uor")
    limit = meta.get("limit", 10)

    eco = get_uor_ecosystem()
    result = eco.moltbook.list_topics(category=category, limit=limit)
    return {"status": "completed", "category": category, **result}


@register_skill("moltbook_search")
def moltbook_search(ctx: PipelineContext) -> Dict[str, Any]:
    """Search moltbook forum posts.

    Metadata:
      query  — search string (required)
      limit  — max results (default 10)
    """
    meta = ctx.goal.metadata or {}
    query = meta.get("query", "")
    if not query:
        return {"status": "failed", "error": "metadata 'query' required"}
    limit = meta.get("limit", 10)

    eco = get_uor_ecosystem()
    result = eco.moltbook.search(query=query, limit=limit)
    return {"status": "completed", "query": query, **result}


@register_skill("moltbook_post")
def moltbook_post(ctx: PipelineContext) -> Dict[str, Any]:
    """Post a new topic to the moltbook forum.

    Requires MOLTBOOK_API_KEY env var.

    Metadata:
      title     — topic title (required)
      body      — topic body (required)
      category  — forum category (default "uor")
    """
    meta = ctx.goal.metadata or {}
    title = meta.get("title", "")
    body = meta.get("body", "")
    if not title or not body:
        return {
            "status": "failed",
            "error": "metadata 'title' and 'body' required",
        }
    category = meta.get("category", "uor")

    eco = get_uor_ecosystem()
    result = eco.moltbook.post_topic(title=title, body=body, category=category)
    return {"status": "completed", "title": title, **result}


# ---------------------------------------------------------------------------
# Prism-BTC skills (placeholder)
# ---------------------------------------------------------------------------

@register_skill("prism_btc_anchor")
def prism_btc_anchor(ctx: PipelineContext) -> Dict[str, Any]:
    """Anchor a UOR digest on the Bitcoin blockchain (placeholder).

    Metadata:
      digest  — sha256:<hex> digest to anchor (required)
    """
    meta = ctx.goal.metadata or {}
    digest = meta.get("digest", "")
    if not digest:
        return {"status": "failed", "error": "metadata 'digest' required"}

    eco = get_uor_ecosystem()
    result = eco.prism_btc.anchor_digest(digest)
    return {"status": "completed", **result}


@register_skill("prism_btc_verify")
def prism_btc_verify(ctx: PipelineContext) -> Dict[str, Any]:
    """Verify an on-chain Bitcoin anchor (placeholder).

    Metadata:
      digest  — sha256:<hex> digest to verify (required)
    """
    meta = ctx.goal.metadata or {}
    digest = meta.get("digest", "")
    if not digest:
        return {"status": "failed", "error": "metadata 'digest' required"}

    eco = get_uor_ecosystem()
    result = eco.prism_btc.verify_anchor(digest)
    return {"status": "completed", **result}


# ---------------------------------------------------------------------------
# Severance AI skills (placeholder)
# ---------------------------------------------------------------------------

@register_skill("severance_infer")
def severance_infer(ctx: PipelineContext) -> Dict[str, Any]:
    """Run inference via Severance AI (placeholder).

    Metadata:
      prompt  — text prompt (required)
      model   — model identifier (default "default")
    """
    meta = ctx.goal.metadata or {}
    prompt = meta.get("prompt", "")
    if not prompt:
        return {"status": "failed", "error": "metadata 'prompt' required"}
    model = meta.get("model", "default")

    eco = get_uor_ecosystem()
    result = eco.severance_ai.infer(prompt, model)
    return {"status": "completed", **result}


@register_skill("severance_verify")
def severance_verify(ctx: PipelineContext) -> Dict[str, Any]:
    """Verify a Severance AI output against criteria (placeholder).

    Metadata:
      output    — text to verify (required)
      criteria  — dict of verification criteria (default {})
    """
    meta = ctx.goal.metadata or {}
    output = meta.get("output", "")
    if not output:
        return {"status": "failed", "error": "metadata 'output' required"}
    criteria = meta.get("criteria", {})

    eco = get_uor_ecosystem()
    result = eco.severance_ai.verify_output(output, criteria)
    return {"status": "completed", **result}


# ---------------------------------------------------------------------------
# Anunix skills (placeholder)
# ---------------------------------------------------------------------------

@register_skill("anunix_health")
def anunix_health(ctx: PipelineContext) -> Dict[str, Any]:
    """Check health of an Anunix-managed host (placeholder).

    Metadata:
      host_id  — host identifier (required)
    """
    meta = ctx.goal.metadata or {}
    host_id = meta.get("host_id", "")
    if not host_id:
        return {"status": "failed", "error": "metadata 'host_id' required"}

    eco = get_uor_ecosystem()
    result = eco.anunix.health_check(host_id)
    return {"status": "completed", **result}


@register_skill("anunix_run")
def anunix_run(ctx: PipelineContext) -> Dict[str, Any]:
    """Run a command on an Anunix host (placeholder).

    Metadata:
      host_id  — host identifier (required)
      command  — shell command to execute (required)
    """
    meta = ctx.goal.metadata or {}
    host_id = meta.get("host_id", "")
    command = meta.get("command", "")
    if not host_id or not command:
        return {
            "status": "failed",
            "error": "metadata 'host_id' and 'command' required",
        }

    eco = get_uor_ecosystem()
    result = eco.anunix.run_command(host_id, command)
    return {"status": "completed", **result}


# ---------------------------------------------------------------------------
# UOR Foundation Live API skill
# ---------------------------------------------------------------------------

@register_skill("uor_foundation_verify")
def uor_foundation_verify(ctx: PipelineContext) -> Dict[str, Any]:
    """Call the live UOR Foundation API verify endpoint.

    Metadata:
      x  — integer parameter (default 42)
    """
    meta = ctx.goal.metadata or {}
    x = meta.get("x", 42)

    eco = get_uor_ecosystem()
    result = eco.uor_foundation.verify(x=x)
    return {"status": "completed", "x": x, **result}


# ---------------------------------------------------------------------------
# Ecosystem status skill
# ---------------------------------------------------------------------------

@register_skill("uor_ecosystem_status")
def uor_ecosystem_status(ctx: PipelineContext) -> Dict[str, Any]:
    """Return overall status of all UOR ecosystem integrations."""
    eco = get_uor_ecosystem()
    return {"status": "completed", "integrations": eco.status()}
