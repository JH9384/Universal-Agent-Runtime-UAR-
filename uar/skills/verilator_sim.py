"""Verilator simulation skill.

A lightweight wrapper that checks for Verilator availability and
returns compilation metadata for SystemVerilog sources.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext


def _check_verilator() -> Dict[str, Any]:
    """Check if Verilator is installed."""
    path = shutil.which("verilator")
    version = "unknown"
    if path:
        try:
            result = subprocess.run(
                ["verilator", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            parts = result.stdout.strip().split()
            version = parts[-1] if parts else "unknown"
        except Exception:
            pass
    return {
        "available": path is not None,
        "path": path,
        "version": version,
    }


def verilator_sim(ctx: PipelineContext) -> Dict[str, Any]:
    """Check Verilator availability and report status.

    Parameters (from ctx.goal.metadata):
        source: str - Optional Verilog source for lint check
    """
    params = ctx.goal.metadata or {}
    source = str(params.get("source", ""))

    info = _check_verilator()

    lint_issues: list = []
    if info["available"] and source.strip():
        # Basic syntax checks without compiling
        if "module" not in source:
            lint_issues.append("No 'module' declaration found")
        if source.count("(") != source.count(")"):
            lint_issues.append("Mismatched parentheses")
        if source.count("{") != source.count("}"):
            lint_issues.append("Mismatched braces")

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "verilator": info,
            "source_length": len(source),
            "lint_issues": lint_issues,
        },
        "metrics": {
            "available": info["available"],
            "issues": len(lint_issues),
        },
    }


register_skill("verilator_sim")(verilator_sim)
