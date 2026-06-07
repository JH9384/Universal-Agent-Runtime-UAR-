"""Integration tests for hardware skill pipeline wiring.

Verifies that myhdl_design → verilog_parse → fpga_verify chain
works without manual source copy-paste, and that quality metrics
are emitted correctly.
"""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.fpga_verify import fpga_verify
from uar.skills.myhdl_design import myhdl_design
from uar.skills.verilog_parse import verilog_parse


def _ctx(meta: dict, data: dict | None = None) -> PipelineContext:
    ctx = PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="test", objective="t", metadata=meta
        )
    )
    if data:
        ctx.data.update(data)
    return ctx


class TestMyhdlToVerilogParse:
    """myhdl_design publishes __verilog_source for downstream skills."""

    def test_myhdl_publishes_verilog_source(self):
        ctx = _ctx({
            "source": "clk = Signal(bool(0))\ndata = Signal(intbv(0)[8:0])",
            "module_name": "counter",
        })
        result = myhdl_design(ctx)
        assert result["status"] == "completed"
        assert "__verilog_source" in ctx.data
        assert "module counter" in ctx.data["__verilog_source"]

    def test_verilog_parse_reads_upstream_source(self):
        """verilog_parse uses __verilog_source when metadata is empty."""
        # Step 1: run myhdl_design
        ctx = _ctx({
            "source": "clk = Signal(bool(0))",
            "module_name": "gate",
        })
        myhdl_design(ctx)

        # Step 2: run verilog_parse with NO source in metadata
        ctx.goal = GoalSpec(
            id="t2", user_intent="test", objective="t2",
            metadata={},
        )
        result = verilog_parse(ctx)
        assert result["status"] == "completed"
        assert result["result"]["module_count"] == 1
        assert result["result"]["modules"][0]["name"] == "gate"

    def test_verilog_parse_prefers_explicit_verilog(self):
        """Explicit Verilog source in metadata is parsed directly."""
        ctx = _ctx({
            "source": "clk = Signal(bool(0))",
            "module_name": "upstream",
        })
        myhdl_design(ctx)

        ctx.goal = GoalSpec(
            id="t2",
            user_intent="test",
            objective="t2",
            metadata={"source": "module explicit (); endmodule"},
        )
        result = verilog_parse(ctx)
        assert result["status"] == "completed"
        assert result["result"]["modules"][0]["name"] == "explicit"

    def test_verilog_parse_skips_myhdl_source(self):
        """MyHDL metadata source is ignored; upstream Verilog is used."""
        ctx = _ctx({
            "source": "clk = Signal(bool(0))",
            "module_name": "gate",
        })
        myhdl_design(ctx)

        # Simulate recipe: same MyHDL source is still in metadata
        ctx.goal = GoalSpec(
            id="t2", user_intent="test", objective="t2",
            metadata={"source": "clk = Signal(bool(0))"},
        )
        result = verilog_parse(ctx)
        assert result["status"] == "completed"
        assert result["result"]["modules"][0]["name"] == "gate"


class TestVerilogParseToFpgaVerify:
    """fpga_verify reads upstream verilog_parse output."""

    def test_fpga_verify_reads_upstream_parse(self):
        """fpga_verify reconstructs source from verilog_parse result."""
        # Step 1: parse some Verilog
        ctx = _ctx({
            "source": (
                "module test (input a, output b);\n"
                "  assign b = a;\n"
                "endmodule\n"
            )
        })
        v_result = verilog_parse(ctx)
        assert v_result["status"] == "completed"
        # Simulate executor writing skill result to ctx.data
        ctx.data["verilog_parse"] = v_result

        # Step 2: verify with NO explicit source
        ctx.goal = GoalSpec(
            id="t2", user_intent="test", objective="t2", metadata={}
        )
        f_result = fpga_verify(ctx)
        assert f_result["status"] == "completed"
        assert f_result["result"]["passed"] > 0

    def test_fpga_verify_reads_verilog_source(self):
        """fpga_verify falls back to raw __verilog_source too."""
        ctx = _ctx({
            "source": "clk = Signal(bool(0))",
            "module_name": "m",
        })
        myhdl_design(ctx)

        # Clear any verilog_parse result that might exist
        ctx.data.pop("verilog_parse", None)
        ctx.goal = GoalSpec(
            id="t2", user_intent="test", objective="t2", metadata={}
        )
        result = fpga_verify(ctx)
        # myhdl stub has no assign statements, so no outputs to check
        assert result["status"] == "completed"


class TestMetrics:
    """Quality metrics are present in hardware skill results."""

    def test_verilog_parse_confidence_metric(self):
        result = verilog_parse(_ctx({
            "source": "module m (input a); endmodule"
        }))
        assert result["status"] == "completed"
        assert result["metrics"]["parse_confidence"] == 1.0

    def test_fpga_verify_assertion_metrics(self):
        result = fpga_verify(_ctx({
            "source": (
                "module t (input a, output b);\n"
                "  assign b = a;\n"
                "endmodule\n"
            ),
            "num_vectors": 4,
        }))
        assert result["status"] == "completed"
        assert "assertion_count" in result["metrics"]
        assert "failed_assertions" in result["metrics"]
        assert result["metrics"]["pass_rate"] == 100.0

    def test_myhdl_stub_lines_metric(self):
        result = myhdl_design(_ctx({
            "source": "clk = Signal(bool(0))",
            "module_name": "m",
        }))
        assert result["status"] == "completed"
        assert result["metrics"]["stub_lines"] > 0

    def test_riscv_completion_ratio(self):
        from uar.skills.riscv_sim import riscv_simulation
        result = riscv_simulation(_ctx({
            "assembly": "addi x1, x0, 5\necall",
            "max_steps": 100,
        }))
        assert result["status"] == "completed"
        assert "completion_ratio" in result["metrics"]
        assert result["metrics"]["completion_ratio"] < 1.0


class TestExecutorPipeline:
    """End-to-end executor tests for hardware recipes."""

    def test_hw_full_recipe_executor(self):
        """Executor runs hw_full with MyHDL source end-to-end."""
        from uar.core.contracts import GoalSpec
        from uar.core.executor import Executor
        from uar.core.planner import SimplePlanner

        goal = GoalSpec(
            id="hw-e2e",
            user_intent="Design and verify a counter",
            objective="hw_full test",
            metadata={
                "source": "clk = Signal(bool(0))\nout = Signal(intbv(0)[8:0])",
                "module_name": "counter",
                "num_vectors": 4,
                "execution_order": [
                    {"type": "recipe", "content": "hw_full", "id": "r1"},
                ],
            },
        )
        strategy = SimplePlanner().plan(goal)
        executor = Executor()
        result = executor.run(strategy, goal, timeout_seconds=30.0)

        assert result.status == "completed"
        # Verify all three skills ran
        skill_events = [
            e for e in result.events
            if e.get("type") == "skill_complete"
        ]
        skill_names = {e.get("skill", "") for e in skill_events}
        assert "myhdl_design" in skill_names
        assert "verilog_parse" in skill_names
        assert "fpga_verify" in skill_names
