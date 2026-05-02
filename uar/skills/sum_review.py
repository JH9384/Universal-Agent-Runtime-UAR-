from uar.core.registry import register_skill


@register_skill("sum_review")
def sum_review(ctx):
    insights = {
        "skills_executed": list(ctx.data.keys()),
        "events_count": len(ctx.events),
        "observations": "Pipeline executed successfully"
    }
    return insights
