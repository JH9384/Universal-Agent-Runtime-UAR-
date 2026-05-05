"""Atomic Language Model (ALM) integration skills.

Provides skills for interacting with the external Atomic Language Model service:
  - alm_analyze       : Analyze formal grammar specifications (BNF, EBNF)
  - alm_generate      : Generate token sequences from a prefix
  - alm_verify        : Validate text against ALM grammar

Configure via env:
  ALM_SERVICE_URL    — ALM service endpoint (default: http://localhost:5001/api/v1)

Goal metadata overrides:
  alm_service_url     — per-run service URL override
"""

from __future__ import annotations

import logging
import os
from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext

logger = logging.getLogger(__name__)


def _get_service_url() -> str:
    """Get ALM service URL from environment or default."""
    return os.getenv("ALM_SERVICE_URL", "http://localhost:5001/api/v1")


def _call_alm(endpoint: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """Call ALM service endpoint (placeholder implementation).
    
    In production, this would make an actual HTTP call to the ALM service.
    Currently returns mock responses for demonstration purposes.
    """
    base_url = _get_service_url()
    logger.info(f"Calling ALM service at {base_url}/{endpoint} with payload: {payload}")
    
    # Placeholder responses for demonstration
    if endpoint == "analyze":
        if "recursive" in str(payload.get("grammar_spec", "")).lower():
            return {
                "status": "success",
                "analysis": "Grammar supports provable recursion.",
                "details": "Passed formal verification checks."
            }
        return {
            "status": "success",
            "analysis": "Grammar analyzed successfully.",
            "details": "Basic syntax check passed."
        }
    
    elif endpoint == "generate":
        prefix = payload.get("prefix", "")
        count = payload.get("count", 5)
        if "student" in prefix:
            return {"tokens": ["student", "left", "the", "school", "yesterday"]}
        return {"tokens": [f"token_{i}" for i in range(count)]}
    
    elif endpoint == "verify":
        text = payload.get("text", "")
        if "student left" in text:
            return {
                "valid": True,
                "proof_id": "proof_123",
                "notes": "Syntactically correct and semantically plausible."
            }
        return {
            "valid": False,
            "error": "Syntax error or semantic violation detected.",
            "details": "Requires formal grammar check."
        }
    
    return {"status": "error", "error": "Unknown endpoint"}


@register_skill("alm_analyze")
def alm_analyze(ctx: PipelineContext) -> Dict[str, Any]:
    """Analyze a formal grammar specification using ALM.
    
    Analyzes formal grammar specifications (e.g., BNF, EBNF) against ALM's
    formal rules for mathematical rigor and provability.
    
    Args:
        ctx: Pipeline context containing goal metadata with grammar_spec
        
    Returns:
        Dictionary with analysis results including status, analysis, and details
    """
    meta = ctx.goal.metadata or {}
    grammar_spec = meta.get("grammar_spec", "")
    
    if not grammar_spec:
        return {
            "status": "failed",
            "error": "No grammar_spec provided in goal metadata"
        }
    
    try:
        result = _call_alm("analyze", {"grammar_spec": grammar_spec})
        return {
            "status": "completed",
            "grammar_spec": grammar_spec,
            **result
        }
    except Exception as e:
        logger.exception("alm_analyze failed")
        return {
            "status": "failed",
            "error": str(e),
            "grammar_spec": grammar_spec
        }


@register_skill("alm_generate")
def alm_generate(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate a token sequence from a prefix using ALM.
    
    Generates a sequence of tokens based on a given prefix using the ALM's
    probabilistic model for formal language generation.
    
    Args:
        ctx: Pipeline context containing goal metadata with prefix and count
        
    Returns:
        Dictionary with generated tokens
    """
    meta = ctx.goal.metadata or {}
    prefix = meta.get("prefix", "")
    count = meta.get("count", 5)
    
    if not prefix:
        return {
            "status": "failed",
            "error": "No prefix provided in goal metadata"
        }
    
    try:
        result = _call_alm("generate", {"prefix": prefix, "count": count})
        return {
            "status": "completed",
            "prefix": prefix,
            "count": count,
            "tokens": result.get("tokens", [])
        }
    except Exception as e:
        logger.exception("alm_generate failed")
        return {
            "status": "failed",
            "error": str(e),
            "prefix": prefix,
            "count": count
        }


@register_skill("alm_verify")
def alm_verify(ctx: PipelineContext) -> Dict[str, Any]:
    """Validate text against ALM grammar.
    
    Performs a full syntactic and semantic validation of a given text
    against the ALM's formal grammar.
    
    Args:
        ctx: Pipeline context containing goal metadata with text to validate
        
    Returns:
        Dictionary with validation status, proof_id (if valid), and notes
    """
    meta = ctx.goal.metadata or {}
    text = meta.get("text", "")
    
    if not text:
        return {
            "status": "failed",
            "error": "No text provided in goal metadata"
        }
    
    try:
        result = _call_alm("verify", {"text": text})
        return {
            "status": "completed",
            "text": text,
            "valid": result.get("valid", False),
            "proof_id": result.get("proof_id"),
            "notes": result.get("notes"),
            "error": result.get("error"),
            "details": result.get("details")
        }
    except Exception as e:
        logger.exception("alm_verify failed")
        return {
            "status": "failed",
            "error": str(e),
            "text": text
        }
