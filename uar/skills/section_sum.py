from uar.core.registry import register_skill


@register_skill("section_sum")
def section_sum(ctx):
    summary = f"Processed goal: {ctx.goal.objective}"
    return {"summary": summary}
