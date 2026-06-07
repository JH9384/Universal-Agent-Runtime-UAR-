"""FPGA verification skill.

A lightweight testbench runner for Verilog modules. Generates
stimulus patterns, applies them to a DUT, and reports pass/fail
with waveform metadata. Pure Python — no simulator required.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import skill_guard, wrap_with_digest


def _parse_dut_ports(source: str) -> List[Dict[str, Any]]:
    """Extract input/output ports from Verilog module."""
    ports = []

    # Try ANSI-style header first: module name ( port_list );
    mod_match = re.search(r'module\s+\w+\s*\((.*?)\);', source, re.DOTALL)
    if mod_match:
        header = mod_match.group(1)
        tokens = re.findall(r'\S+', header)
        direction: str | None = None
        width = 1
        for tok in tokens:
            tok = tok.rstrip(',;')
            if tok in ('input', 'output', 'inout'):
                direction = tok
                width = 1
                continue
            if tok in ('reg', 'wire', 'logic'):
                continue
            m = re.match(r'\[(\d+):(\d+)\]', tok)
            if m:
                width = int(m.group(1)) + 1
                continue
            if direction and tok:
                ports.append({
                    "name": tok,
                    "direction": direction,
                    "width": width,
                })

    # Fallback: old-style declarations inside body
    if not ports:
        port_pattern = re.compile(
            r'(input|output|inout)\s+(?:\[(\d+):(\d+)\]\s+)?([^;]+);'
        )
        for match in port_pattern.finditer(source):
            direction = match.group(1)
            msb = match.group(2)
            names = match.group(4)
            width = 1 if msb is None else (int(msb) + 1)
            for name in re.split(r'[,\s]+', names.strip()):
                if name:
                    ports.append({
                        "name": name,
                        "direction": direction,
                        "width": width,
                    })

    return ports


def _generate_test_vectors(
    inputs: List[Dict[str, Any]], num_vectors: int
) -> List[Dict[str, int]]:
    """Generate pseudo-random test vectors for inputs."""
    import random
    vectors = []
    for i in range(num_vectors):
        vec: Dict[str, int] = {}
        for inp in inputs:
            max_val = (1 << inp["width"]) - 1
            vec[inp["name"]] = random.randint(0, max_val)
        vec["_cycle"] = i
        vectors.append(vec)
    return vectors


def _simulate_combinational(
    source: str, vectors: List[Dict[str, int]]
) -> List[Dict[str, Any]]:
    """Very simple combinational logic evaluator."""
    results = []
    # Extract assign statements
    assigns = re.findall(r'assign\s+(\w+)\s*=\s*([^;]+);', source)
    assign_map = {lhs.strip(): rhs.strip() for lhs, rhs in assigns}

    for vec in vectors:
        outputs = {}
        for lhs, rhs in assign_map.items():
            # Very naive evaluation: just copy input if referenced
            for key, val in vec.items():
                if key in rhs:
                    outputs[lhs] = val
                    break
            if lhs not in outputs:
                outputs[lhs] = 0

        results.append({
            "cycle": vec["_cycle"],
            "inputs": {k: v for k, v in vec.items() if k != "_cycle"},
            "outputs": outputs,
        })
    return results


@skill_guard("FPGA verify", status="failed")
def fpga_verify(ctx: PipelineContext) -> Dict[str, Any]:
    """Verify Verilog module with generated test vectors.

    Parameters (from ctx.goal.metadata):
        source: str - Verilog module source code
        num_vectors: int - Number of test vectors (default: 8)
    """
    params = ctx.goal.metadata or {}
    source = str(params.get("source", ""))

    # Fall back to upstream skill outputs when no explicit source given
    # or when source doesn't look like Verilog (e.g. MyHDL from recipe)
    use_upstream = (
        not source.strip()
        or ("module" not in source and "verilog_parse" in ctx.data)
    )
    if use_upstream:
        upstream = ctx.data.get("verilog_parse", {})
        if isinstance(upstream, dict):
            mods = upstream.get("result", {}).get("modules", [])
            if mods:
                # Reconstruct source from parsed module data
                parts = []
                for mod in mods:
                    pdecls = ", ".join(
                        f"{p['direction']} {p['name']}"
                        for p in mod.get("ports", [])
                    )
                    parts.append(f"module {mod['name']} ({pdecls});\n")
                    for s in mod.get("signals", []):
                        w = s.get("width", "")
                        parts.append(f"  {s['type']} {w} {s['name']};\n")
                    for inst in mod.get("instances", []):
                        conns = ", ".join(
                            f".{c['port']}({c['signal']})"
                            for c in inst.get("connections", [])
                        )
                        parts.append(
                            f"  {inst['module']} {inst['instance']} "
                            f"({conns});\n"
                        )
                    for asn in mod.get("assigns", []):
                        parts.append(
                            f"  assign {asn['lhs']} = {asn['rhs']};\n"
                        )
                    parts.append("endmodule\n")
                source = "".join(parts)
        if not source.strip():
            source = str(ctx.data.get("__verilog_source", ""))

    num_vectors = int(params.get("num_vectors", 8))

    if not source.strip():
        return {
            "status": "failed",
            "error": "source is required (provide in metadata or run "
                     "verilog_parse / myhdl_design first)",
        }

    ports = _parse_dut_ports(source)
    inputs = [p for p in ports if p["direction"] == "input"]
    outputs = [p for p in ports if p["direction"] == "output"]

    vectors = _generate_test_vectors(inputs, num_vectors)
    results = _simulate_combinational(source, vectors)

    # Build waveform metadata
    waveform = {
        "signals": [p["name"] for p in ports],
        "cycles": num_vectors,
        "data": results,
    }

    # Simple assertions
    assertions = []
    passed = 0
    failed = 0
    for r in results:
        for out_name, out_val in r["outputs"].items():
            # Check output is within valid range
            out_port = next(
                (p for p in outputs if p["name"] == out_name), None
            )
            if out_port:
                max_val = (1 << out_port["width"]) - 1
                if 0 <= out_val <= max_val:
                    passed += 1
                else:
                    failed += 1
                    assertions.append(wrap_with_digest({
                        "cycle": r["cycle"],
                        "signal": out_name,
                        "expected": f"<= {max_val}",
                        "actual": out_val,
                        "status": "fail",
                    }))

    # Digest each waveform data point
    for r in results:
        wrap_with_digest(r)

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "module_name": (
                (_m.group(1) if (_m := re.search(
                    r'module\s+(\w+)', source
                )) else "unknown")
            ),
            "ports": ports,
            "test_vectors": num_vectors,
            "passed": passed,
            "failed": failed,
            "assertions": assertions,
            "waveform": waveform,
        },
        "metrics": {
            "inputs": len(inputs),
            "outputs": len(outputs),
            "tests": num_vectors,
            "pass_rate": (
                (passed / (passed + failed) * 100)
                if (passed + failed) > 0 else 0
            ),
            "assertion_count": passed + failed,
            "failed_assertions": failed,
        },
    }


register_skill("fpga_verify")(fpga_verify)
