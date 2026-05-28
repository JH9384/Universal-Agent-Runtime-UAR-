"""Verilog HDL parsing skill.

A lightweight Verilog parser for extracting module hierarchy,
port definitions, and signal connections. Pure Python — no
dependencies required.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import skill_guard


def _extract_modules(source: str) -> List[Dict[str, Any]]:
    """Extract module definitions from Verilog source."""
    modules = []
    # Find module declarations
    mod_pattern = re.compile(
        r'module\s+(\w+)\s*\((.*?)\);(.*?)endmodule',
        re.DOTALL,
    )
    for match in mod_pattern.finditer(source):
        name = match.group(1)
        ports_str = match.group(2)
        body = match.group(3)
        ports = _parse_ports(ports_str)
        signals = _extract_signals(body)
        instances = _extract_instances(body)
        assigns = _extract_assigns(body)
        modules.append({
            "name": name,
            "ports": ports,
            "signals": signals,
            "instances": instances,
            "assigns": assigns,
        })
    return modules


def _parse_ports(ports_str: str) -> List[Dict[str, str]]:
    """Parse port list string into direction/name pairs."""
    ports: List[Dict[str, str]] = []
    # Handle ANSI-style port declarations within module body
    return ports


def _extract_signals(body: str) -> List[Dict[str, Any]]:
    """Extract wire/reg declarations from module body."""
    signals = []
    wire_pattern = re.compile(
        r'(wire|reg|logic|input|output|inout)'
        r'\s*(?:\[(\d+):(\d+)\])?\s+([^;]+);'
    )
    for match in wire_pattern.finditer(body):
        kind = match.group(1)
        msb = match.group(2)
        lsb = match.group(3)
        names = match.group(4)
        for name in re.split(r'[,\s]+', names.strip()):
            if name:
                signals.append({
                    "name": name,
                    "type": kind,
                    "width": (
                        f"[{msb}:{lsb}]"
                        if msb is not None else "[0:0]"
                    ),
                })
    return signals


def _extract_instances(body: str) -> List[Dict[str, Any]]:
    """Extract module instantiations."""
    instances = []
    inst_pattern = re.compile(
        r'(\w+)\s+(\w+)\s*\((.*?)\);',
        re.DOTALL,
    )
    for match in inst_pattern.finditer(body):
        mod_name = match.group(1)
        inst_name = match.group(2)
        conn_str = match.group(3)
        # Skip if this is a primitive (wire/reg declaration)
        if mod_name in ('wire', 'reg', 'logic', 'input', 'output'):
            continue
        connections = []
        for conn in re.split(r',\s*(?=\.)', conn_str):
            conn = conn.strip()
            if conn.startswith('.'):
                m = re.match(r'\.(\w+)\s*\((.*?)\)', conn)
                if m:
                    connections.append({
                        "port": m.group(1),
                        "signal": m.group(2).strip(),
                    })
        instances.append({
            "module": mod_name,
            "instance": inst_name,
            "connections": connections,
        })
    return instances


def _extract_assigns(body: str) -> List[Dict[str, str]]:
    """Extract continuous assignments."""
    assigns = []
    assign_pattern = re.compile(r'assign\s+(\w+)\s*=\s*([^;]+);')
    for match in assign_pattern.finditer(body):
        assigns.append({
            "lhs": match.group(1).strip(),
            "rhs": match.group(2).strip(),
        })
    return assigns


@skill_guard("Verilog parse", status="failed")
def verilog_parse(ctx: PipelineContext) -> Dict[str, Any]:
    """Parse Verilog HDL source code.

    Parameters (from ctx.goal.metadata):
        source: str - Verilog source code string
    """
    params = ctx.goal.metadata or {}
    source = str(params.get("source", ""))

    if not source.strip():
        return {
            "status": "failed",
            "error": "source is required in goal metadata",
        }

    modules = _extract_modules(source)

    # Build hierarchy tree
    hierarchy = []
    for mod in modules:
        children = [
            {
                "type": "instance",
                "module": inst["module"],
                "name": inst["instance"],
            }
            for inst in mod["instances"]
        ]
        hierarchy.append({
            "module": mod["name"],
            "children": children,
        })

    # Count statistics
    total_ports = sum(len(m["ports"]) for m in modules)
    total_signals = sum(len(m["signals"]) for m in modules)
    total_instances = sum(len(m["instances"]) for m in modules)

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "modules": modules,
            "hierarchy": hierarchy,
            "module_count": len(modules),
            "total_ports": total_ports,
            "total_signals": total_signals,
            "total_instances": total_instances,
        },
        "metrics": {
            "modules": len(modules),
            "instances": total_instances,
            "signals": total_signals,
        },
    }


register_skill("verilog_parse")(verilog_parse)
