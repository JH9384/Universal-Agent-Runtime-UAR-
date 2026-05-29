"""Alias skills — thin wrappers that register alternative names for existing skills.

Imported before stub_skills so aliases take precedence over stubs.
"""

from __future__ import annotations

from typing import Any, Dict

from uar.core.contracts import PipelineContext
from uar.core.registry import register_skill
from uar.core.skill_utils import skill_guard

# Import the real skills we alias to
from uar.skills.autonomi_storage import (
    autonomi_download,
    autonomi_status,
    autonomi_upload,
)
from uar.skills.dependency_map import dependency_map
from uar.skills.graphrag_skills import (
    graphrag_index,
    graphrag_init,
    graphrag_query,
)
from uar.skills.sum_review import sum_review
from uar.skills.uor_ecosystem_skills import (
    uor_addr_canonicalize,
    uor_ecosystem_status,
    uor_foundation_verify,
)


# ---------------------------------------------------------------------------
# Autonomi aliases
# ---------------------------------------------------------------------------

@register_skill("auto_down")
@skill_guard("Auto down")
def auto_down(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for autonomi_download."""
    return autonomi_download(ctx)


@register_skill("auto_status")
@skill_guard("Auto status")
def auto_status(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for autonomi_status."""
    return autonomi_status(ctx)


@register_skill("auto_up")
@skill_guard("Auto up")
def auto_up(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for autonomi_upload."""
    return autonomi_upload(ctx)


# ---------------------------------------------------------------------------
# Utility aliases
# ---------------------------------------------------------------------------

@register_skill("deps")
@skill_guard("Deps")
def deps(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for dependency_map."""
    return dependency_map(ctx)


@register_skill("review")
@skill_guard("Review")
def review(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for sum_review."""
    return sum_review(ctx)


# ---------------------------------------------------------------------------
# UOR ecosystem aliases
# ---------------------------------------------------------------------------

@register_skill("eco_canon")
@skill_guard("Eco canon")
def eco_canon(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for uor_addr_canonicalize."""
    return uor_addr_canonicalize(ctx)


@register_skill("eco_foundation")
@skill_guard("Eco foundation")
def eco_foundation(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for uor_foundation_verify."""
    return uor_foundation_verify(ctx)


@register_skill("eco_status")
@skill_guard("Eco status")
def eco_status(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for uor_ecosystem_status."""
    return uor_ecosystem_status(ctx)


# ---------------------------------------------------------------------------
# GraphRAG aliases
# ---------------------------------------------------------------------------

@register_skill("gr_index")
@skill_guard("Gr index")
def gr_index(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for graphrag_index."""
    return graphrag_index(ctx)


@register_skill("gr_query")
@skill_guard("Gr query")
def gr_query(ctx: PipelineContext) -> Dict[str, Any]:
    """Alias for graphrag_query."""
    return graphrag_query(ctx)


@register_skill("gr_full")
@skill_guard("Gr full")
def gr_full(ctx: PipelineContext) -> Dict[str, Any]:
    """Composite: init + index + query.

    Runs graphrag_init, graphrag_index, then graphrag_query in sequence.
    Metadata from each step flows forward.
    """
    results = {}

    # Init
    r1 = graphrag_init(ctx)
    results["init"] = r1
    if r1.get("status") != "completed":
        return {"status": "failed", "stage": "init", **r1}

    # Index
    r2 = graphrag_index(ctx)
    results["index"] = r2
    if r2.get("status") != "completed":
        return {"status": "failed", "stage": "index", **results}

    # Query
    r3 = graphrag_query(ctx)
    results["query"] = r3
    if r3.get("status") != "completed":
        return {"status": "failed", "stage": "query", **results}

    return {"status": "completed", "stages": results}
