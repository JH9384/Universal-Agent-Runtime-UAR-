"""Tests for FPGA verification skill.

Covers assertion counting, port parsing, combinational simulation,
and the skill entry point.
"""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.fpga_verify import (
    _parse_dut_ports,
    _simulate_combinational,
    fpga_verify,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="test", objective="t", metadata=meta
        )
    )


class TestAssertionCounting:
    """Bug: passed was doubled before any failure occurred."""

    def test_all_pass_no_inflation(self):
        """All outputs in range: passed must equal vectors x outputs."""
        source = (
            "module test (input a, input b, output [1:0] y);\n"
            "    assign y = a & b;\n"
            "endmodule\n"
        )
        result = fpga_verify(_ctx({"source": source, "num_vectors": 4}))
        assert result["status"] == "completed"
        assert result["result"]["passed"] == 4
        assert result["result"]["failed"] == 0

    def test_some_fail_no_inflation(self):
        """Some outputs out of range: total checks = passed + failed."""
        # 3-bit input (0-7) copied to 2-bit output (0-3): values 4-7 fail
        source = (
            "module test (input [2:0] a, output [1:0] y);\n"
            "    assign y = a;\n"
            "endmodule\n"
        )
        with patch("random.randint", side_effect=[0, 1, 4, 7, 0, 1, 2, 3]):
            result = fpga_verify(
                _ctx({"source": source, "num_vectors": 4})
            )
        assert result["status"] == "completed"
        assert result["result"]["failed"] == 2
        assert result["result"]["passed"] == 2
        assert result["result"]["passed"] + result["result"]["failed"] == 4

    def test_fail_then_pass_counts_correctly(self):
        """A failing vector followed by passing ones: no inflation."""
        source = (
            "module test (input [2:0] a, output [1:0] y);\n"
            "    assign y = a;\n"
            "endmodule\n"
        )
        with patch("random.randint", side_effect=[7, 0, 1, 2]):
            result = fpga_verify(
                _ctx({"source": source, "num_vectors": 4})
            )
        assert result["status"] == "completed"
        assert result["result"]["failed"] == 1
        assert result["result"]["passed"] == 3


class TestPortParsing:
    """DUT port extraction."""

    def test_bus_width_parsed(self):
        source = "module m (input [7:0] data); endmodule"
        ports = _parse_dut_ports(source)
        assert len(ports) == 1
        assert ports[0]["width"] == 8

    def test_multiple_ports(self):
        source = "module m (input a, output b, inout c); endmodule"
        ports = _parse_dut_ports(source)
        assert len(ports) == 3


class TestSimulation:
    """Combinational logic evaluator."""

    def test_assign_copy(self):
        source = "assign y = a;"
        vectors = [{"a": 1, "_cycle": 0}]
        results = _simulate_combinational(source, vectors)
        assert results[0]["outputs"]["y"] == 1

    def test_default_zero(self):
        source = "assign y = b;"
        vectors = [{"a": 1, "_cycle": 0}]  # b missing
        results = _simulate_combinational(source, vectors)
        assert results[0]["outputs"]["y"] == 0
