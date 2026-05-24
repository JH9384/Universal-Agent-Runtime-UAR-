"""Example external UAR skill plugin.

This module demonstrates both registration patterns:
1. ``@register_skill`` decorator (automatic on import)
2. ``__uar_skills__`` dict export (fallback for dynamic registration)
"""

from uar.core.registry import register_skill


@register_skill("example_hello")
def example_hello(ctx):
    """Say hello from an external plugin."""
    return {
        "status": "completed",
        "message": "Hello from uar-skills-example!",
        "plugin": "uar-skills-example",
    }


@register_skill("example_echo")
def example_echo(ctx):
    """Echo back the goal metadata."""
    metadata = getattr(ctx, "goal", {}).get("metadata", {})
    return {
        "status": "completed",
        "echo": metadata,
    }


# Optional: export a dict for manual registration
__uar_skills__ = {
    "example_hello": example_hello,
    "example_echo": example_echo,
}
