"""Tests for MyHDL hardware design skill.

Covers _parse_python_hdl, _generate_verilog_stub, and myhdl_design.
"""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.myhdl_design import (
    _parse_python_hdl,
    _generate_verilog_stub,
    myhdl_design,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="test", objective="t", metadata=meta
        )
    )


class TestParsePythonHdl:
    """Python HDL parser."""

    def test_empty(self):
        result = _parse_python_hdl("")
        assert result["signals"] == []

    def test_signal(self):
        result = _parse_python_hdl("clk = Signal(0)")
        assert len(result["signals"]) == 1
        assert result["signals"][0]["name"] == "0"
        assert result["signals"][0]["type"] == "Signal"

    def test_intbv(self):
        source = "count = Signal(intbv(0)[8:])"
        result = _parse_python_hdl(source)
        assert len(result["signals"]) == 1  # Only intbv pattern matches


class TestGenerateVerilogStub:
    """Verilog stub generation."""

    def test_empty(self):
        stub = _generate_verilog_stub("test", [])
        assert "module test" in stub
        assert "endmodule" in stub

    def test_with_signals(self):
        signals = [{"name": "clk", "width": 1}, {"name": "data", "width": 8}]
        stub = _generate_verilog_stub("my_mod", signals)
        assert "module my_mod" in stub
        assert "input clk;" in stub
        assert "input [7:0] data;" in stub
        assert "endmodule" in stub


class TestMyhdlDesignSkill:
    """Skill entry point."""

    def test_empty_source(self):
        result = myhdl_design(_ctx({"source": ""}))
        assert result["status"] == "failed"
        assert "required" in result["error"].lower()

    def test_basic_source(self):
        result = myhdl_design(_ctx({
            "source": "clk = Signal(bool(0))",
            "module_name": "counter",
        }))
        assert result["status"] == "completed"
        assert result["result"]["module_name"] == "counter"
        assert "verilog_stub" in result["result"]
        assert "myhdl_available" in result["result"]

    def test_default_module_name(self):
        result = myhdl_design(_ctx({"source": "s = Signal(0)"}))
        assert result["result"]["module_name"] == "myhdl_module"
