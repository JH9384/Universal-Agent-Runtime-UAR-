"""Tests for uar.skills.verilog_parse — Verilog HDL parsing skill."""

from uar.skills.verilog_parse import (
    _extract_assigns,
    _extract_instances,
    _extract_modules,
    _extract_signals,
    _parse_ports,
    verilog_parse,
)
from uar.core.contracts import GoalSpec, PipelineContext


# ── Sample Verilog source ───────────────────────────────────────────────────

_SAMPLE_COUNTER = """
module counter (
    input clk,
    input rst,
    output reg [7:0] count
);
    wire enable;
    reg [3:0] state;

    assign enable = 1'b1;

    adder u_adder (
        .a(count),
        .b(8'd1),
        .sum(next_count)
    );
endmodule
"""

_SAMPLE_EMPTY = """
module empty ();
endmodule
"""

_SAMPLE_MULTI = """
module foo (input a, output b);
    wire x;
    assign b = a & x;
endmodule

module bar (input c, output d);
    reg y;
    assign d = c | y;
endmodule
"""

# ── _extract_modules ────────────────────────────────────────────────────────


def test_extract_modules_finds_counter():
    modules = _extract_modules(_SAMPLE_COUNTER)
    assert len(modules) == 1
    mod = modules[0]
    assert mod["name"] == "counter"


def test_extract_modules_multi():
    modules = _extract_modules(_SAMPLE_MULTI)
    assert len(modules) == 2
    names = {m["name"] for m in modules}
    assert names == {"foo", "bar"}


def test_extract_modules_empty_body():
    modules = _extract_modules(_SAMPLE_EMPTY)
    assert len(modules) == 1
    assert modules[0]["name"] == "empty"


def test_extract_modules_no_modules():
    modules = _extract_modules("// just a comment")
    assert modules == []


# ── _parse_ports ───────────────────────────────────────────────────────────


def test_parse_ports_ansi_style():
    ports = _parse_ports("input clk, input rst, output reg [7:0] count")
    assert len(ports) == 3
    names = {p["name"] for p in ports}
    assert names == {"clk", "rst", "count"}
    directions = {p["direction"] for p in ports}
    assert directions == {"input", "output"}


def test_parse_ports_simple_names():
    ports = _parse_ports("a, b, c")
    assert len(ports) == 3
    names = {p["name"] for p in ports}
    assert names == {"a", "b", "c"}
    for p in ports:
        assert p["direction"] == "unknown"


def test_parse_ports_empty():
    ports = _parse_ports("")
    assert ports == []


# ── _extract_signals ────────────────────────────────────────────────────────


def test_extract_signals_wire_reg():
    body = "wire enable; reg [3:0] state; logic [7:0] data;"
    signals = _extract_signals(body)
    names = {s["name"] for s in signals}
    assert names == {"enable", "state", "data"}


def test_extract_signals_widths():
    body = "wire [31:0] bus; reg [0:0] bit;"
    signals = _extract_signals(body)
    bus = next(s for s in signals if s["name"] == "bus")
    assert bus["width"] == "[31:0]"
    bit = next(s for s in signals if s["name"] == "bit")
    assert bit["width"] == "[0:0]"


def test_extract_signals_multi_names():
    body = "wire a, b, c;"
    signals = _extract_signals(body)
    assert len(signals) == 3
    names = {s["name"] for s in signals}
    assert names == {"a", "b", "c"}


def test_extract_signals_input_output():
    body = "input [7:0] din; output [3:0] dout; inout bidir;"
    signals = _extract_signals(body)
    assert len(signals) == 3
    kinds = {s["type"] for s in signals}
    assert kinds == {"input", "output", "inout"}


# ── _extract_instances ─────────────────────────────────────────────────────


def test_extract_instances_adder():
    body = """
    adder u_adder (
        .a(count),
        .b(8'd1),
        .sum(next_count)
    );
    """
    instances = _extract_instances(body)
    assert len(instances) == 1
    inst = instances[0]
    assert inst["module"] == "adder"
    assert inst["instance"] == "u_adder"
    assert len(inst["connections"]) == 3
    ports = {c["port"] for c in inst["connections"]}
    assert ports == {"a", "b", "sum"}


def test_extract_instances_skips_primitives():
    body = "wire x; reg y; logic z;"
    instances = _extract_instances(body)
    assert instances == []


def test_extract_instances_no_paren_connections():
    body = "my_mod u1 (a, b, c);"
    instances = _extract_instances(body)
    assert len(instances) == 1
    assert instances[0]["module"] == "my_mod"


# ── _extract_assigns ─────────────────────────────────────────────────────────


def test_extract_assigns_basic():
    body = "assign out = in1 & in2;"
    assigns = _extract_assigns(body)
    assert len(assigns) == 1
    assert assigns[0]["lhs"] == "out"
    assert assigns[0]["rhs"] == "in1 & in2"


def test_extract_assigns_multi():
    body = "assign a = b; assign c = d ^ e;"
    assigns = _extract_assigns(body)
    assert len(assigns) == 2


def test_extract_assigns_none():
    assigns = _extract_assigns("wire x;")
    assert assigns == []


# ── verilog_parse (skill entry point) ────────────────────────────────────────


def _make_ctx(source: str) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="g1",
            user_intent="parse verilog",
            objective="test",
            metadata={"source": source},
        )
    )


def test_verilog_parse_success():
    ctx = _make_ctx(_SAMPLE_COUNTER)
    result = verilog_parse(ctx)
    assert result["status"] == "completed"
    res = result["result"]
    assert res["module_count"] == 1
    assert res["total_signals"] > 0
    assert res["total_instances"] > 0
    assert len(res["hierarchy"]) == 1


def test_verilog_parse_multi_modules():
    ctx = _make_ctx(_SAMPLE_MULTI)
    result = verilog_parse(ctx)
    assert result["status"] == "completed"
    assert result["result"]["module_count"] == 2


def test_verilog_parse_empty_source():
    ctx = _make_ctx("")
    result = verilog_parse(ctx)
    assert result["status"] == "failed"
    assert "source is required" in result["error"]


def test_verilog_parse_no_modules():
    ctx = _make_ctx("// nothing here")
    result = verilog_parse(ctx)
    assert result["status"] == "completed"
    assert result["result"]["module_count"] == 0
    assert result["result"]["total_signals"] == 0
