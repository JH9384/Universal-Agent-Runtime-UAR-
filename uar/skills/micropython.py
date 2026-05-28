"""MicroPython for embedded skill.

A lightweight MicroPython code executor for embedded device simulation.
"""

from __future__ import annotations

from typing import Any, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import require_package


def _simulate_execution(code: str) -> Dict[str, Any]:
    """Simulate MicroPython code execution in a safe environment."""
    stdout: list = []
    pins: Dict[str, Any] = {}
    errors: list = []

    for line in code.strip().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        # Simulate pin initialization
        if "machine.Pin(" in line:
            pin_match = __import__("re").search(
                r"Pin\((\d+).*?Pin\.(OUT|IN)", line
            )
            if pin_match:
                pin_num = pin_match.group(1)
                mode = pin_match.group(2)
                pins[f"GPIO{pin_num}"] = {"mode": mode, "value": 0}
                stdout.append(f"Initialized GPIO{pin_num} as {mode}")

        # Simulate pin write
        elif ".value(" in line:
            pin_match = __import__("re").search(
                r"(\w+)\.value\((\d+)\)", line
            )
            if pin_match:
                pin_name = pin_match.group(1)
                val = int(pin_match.group(2))
                pins[pin_name] = pins.get(pin_name, {})
                pins[pin_name]["value"] = val
                stdout.append(f"{pin_name} set to {val}")

        # Simulate print
        elif "print(" in line:
            stdout.append(line)

    return {
        "stdout": stdout,
        "pins": pins,
        "errors": errors,
    }


def micropython(ctx: PipelineContext) -> Dict[str, Any]:
    """Execute MicroPython code for embedded simulation.

    Parameters (from ctx.goal.metadata):
        code: str - MicroPython source code
    """
    params = ctx.goal.metadata or {}
    code = str(params.get("code", ""))

    if not code.strip():
        return {
            "status": "failed",
            "error": "code is required in goal metadata",
        }

    available = require_package("machine") is None
    result = _simulate_execution(code)

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "stdout": result["stdout"],
            "pins": result["pins"],
            "errors": result["errors"],
            "micropython_available": available,
        },
        "metrics": {
            "lines": len([ln for ln in code.splitlines() if ln.strip()]),
            "pins": len(result["pins"]),
            "outputs": len(result["stdout"]),
        },
    }


register_skill("micropython")(micropython)
