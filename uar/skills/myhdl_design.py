"""MyHDL hardware design skill.

A lightweight MyHDL wrapper for Python-to-Verilog/VHDL conversion.
Pure Python — generates Verilog from Python hardware descriptions.
"""

from __future__ import annotations

import re
from typing import Any, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext


def _check_myhdl_available() -> bool:
    import importlib.util
    return importlib.util.find_spec("myhdl") is not None


def _parse_python_hdl(source: str) -> Dict[str, Any]:
    """Parse Python-style HDL description and extract signals."""
    signals = []
    # Match Signal declarations
    sig_pattern = re.compile(
        r'Signal\s*\(\s*(\w+)\s*\)',
        re.IGNORECASE,
    )
    for match in sig_pattern.finditer(source):
        signals.append({
            "name": match.group(1),
            "type": "Signal",
            "width": 1,
        })

    # Match intbv types
    intbv_pattern = re.compile(
        r'(\w+)\s*=\s*Signal\s*\(\s*intbv\s*\((\d+)\)\s*'
        r'\[\s*(\d+)\s*:\s*\]\s*\)',
        re.IGNORECASE,
    )
    for match in intbv_pattern.finditer(source):
        signals.append({
            "name": match.group(1),
            "type": "intbv",
            "width": int(match.group(3)),
            "default": int(match.group(2)),
        })

    return {"signals": signals}


def _generate_verilog_stub(name: str, signals: list) -> str:
    """Generate a Verilog module stub from signal descriptions."""
    lines = [f"module {name} ("]
    port_names = [s["name"] for s in signals]
    lines.append(", ".join(port_names) + ");")

    for sig in signals:
        w = sig.get("width", 1)
        if w > 1:
            lines.append(f"  input [{w - 1}:0] {sig['name']};")
        else:
            lines.append(f"  input {sig['name']};")

    lines.append("")
    lines.append("  // User logic goes here")
    lines.append("")
    lines.append("endmodule")
    return "\n".join(lines)


def myhdl_design(ctx: PipelineContext) -> Dict[str, Any]:
    """Hardware design with MyHDL.

    Parameters (from ctx.goal.metadata):
        source: str - Python/MyHDL source code
        module_name: str - Target module name (default: myhdl_module)
    """
    params = ctx.goal.metadata or {}
    source = str(params.get("source", ""))
    module_name = str(params.get("module_name", "myhdl_module"))

    if not source.strip():
        return {
            "status": "failed",
            "error": "source is required in goal metadata",
        }

    myhdl_available = _check_myhdl_available()
    parsed = _parse_python_hdl(source)
    verilog_stub = _generate_verilog_stub(module_name, parsed["signals"])

    result: Dict[str, Any] = {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "module_name": module_name,
            "signals": parsed["signals"],
            "verilog_stub": verilog_stub,
            "myhdl_available": myhdl_available,
        },
        "metrics": {
            "signals": len(parsed["signals"]),
        },
    }

    if myhdl_available:
        result["result"]["note"] = (
            "MyHDL is available — run 'toVerilog()' for full conversion"
        )
    else:
        result["result"]["note"] = (
            "MyHDL not installed. Install: pip install myhdl"
        )

    return result


register_skill("myhdl_design")(myhdl_design)
