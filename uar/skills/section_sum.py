from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from typing import Dict, Any


@register_skill("section_sum")
def section_sum(ctx: PipelineContext) -> Dict[str, Any]:
    """Generate a summary of the processed goal.

    This skill creates a simple summary message indicating the goal was processed.
    Typically used as the final step in a pipeline to provide closure.

    Args:
        ctx: Pipeline context containing goal information.

    Returns:
        Dictionary with a summary message.
    """  # noqa: E501
    summary = f"Processed goal: {ctx.goal.objective}"
    return {"summary": summary}
