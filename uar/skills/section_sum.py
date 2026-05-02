from uar.core.registry import register_skill


@register_skill("section_sum")
def section_sum():
    return {"summary": "stub summary"}
