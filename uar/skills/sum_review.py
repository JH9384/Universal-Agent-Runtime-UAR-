from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import skill_guard
from typing import Dict, Any


@register_skill("sum_review")
@skill_guard("Sum review")
def sum_review(ctx: PipelineContext) -> Dict[str, Any]:
    """Provide a final review and summary of the pipeline execution.

    This skill aggregates information about the executed skills, events generated,
    and provides an overall assessment of the pipeline run.

    Args:
        ctx: Pipeline context containing execution data and events.

    Returns:
        Dictionary containing skills executed, event count, and observations.
    """  # noqa: E501
    insights = {
        "skills_executed": list(ctx.data.keys()),
        "events_count": len(ctx.events),
        "observations": "Pipeline executed successfully",
    }
    return insights
