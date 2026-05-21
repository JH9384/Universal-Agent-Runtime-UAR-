"""Unit tests for skills added in Batch 43-46.

Covers: riscv_sim, verilog_parse, fpga_verify, myhdl_design,
riscv_cycle, data_viz_3d, stub_skills.
"""

from __future__ import annotations

from uar.core.contracts import PipelineContext, GoalSpec
from uar.skills import (
    riscv_sim,
    verilog_parse,
    fpga_verify,
    myhdl_design,
    riscv_cycle,
    data_viz_3d,
    stub_skills,
)


def _ctx(metadata: dict | None = None) -> PipelineContext:
    goal = GoalSpec(
        id="test-id",
        user_intent="test",
        objective="test",
        metadata=metadata or {},
    )
    return PipelineContext(goal=goal)


# ---------------------------------------------------------------------------
# riscv_sim
# ---------------------------------------------------------------------------

def test_riscv_sim_empty_assembly_fails():
    ctx = _ctx({"assembly": ""})
    result = riscv_sim.riscv_simulation(ctx)
    assert result["status"] == "failed"


def test_riscv_sim_basic_addi():
    ctx = _ctx({
        "assembly": "addi x1, x0, 42\naddi x2, x1, 8",
        "memory_size": 64,
    })
    result = riscv_sim.riscv_simulation(ctx)
    assert result["status"] == "completed"
    assert result["result"]["registers"][1]["value"] == 42
    assert result["result"]["registers"][2]["value"] == 50


def test_riscv_sim_ecall_halts():
    ctx = _ctx({
        "assembly": "addi x1, x0, 1\necall",
        "memory_size": 64,
    })
    result = riscv_sim.riscv_simulation(ctx)
    assert result["status"] == "completed"
    assert result["result"]["registers"][1]["value"] == 1


# ---------------------------------------------------------------------------
# verilog_parse
# ---------------------------------------------------------------------------

def test_verilog_parse_empty():
    ctx = _ctx({"source": ""})
    result = verilog_parse.verilog_parse(ctx)
    assert result["status"] == "failed"


def test_verilog_parse_simple_module():
    source = """
module adder(input [31:0] a, input [31:0] b, output [31:0] sum);
  assign sum = a + b;
endmodule
"""
    ctx = _ctx({"source": source})
    result = verilog_parse.verilog_parse(ctx)
    assert result["status"] == "completed"
    assert result["result"]["module_count"] == 1
    assert result["result"]["modules"][0]["name"] == "adder"


def test_verilog_parse_extracts_signals_and_assigns():
    source = """
module mux(a, b, sel, y);
  input a;
  input b;
  input sel;
  output y;
  wire sel_n;
  assign sel_n = ~sel;
  assign y = sel ? b : a;
endmodule
"""
    ctx = _ctx({"source": source})
    result = verilog_parse.verilog_parse(ctx)
    assert result["status"] == "completed"
    mod = result["result"]["modules"][0]
    assert mod["name"] == "mux"
    assert len(mod["signals"]) >= 4
    assert len(mod["assigns"]) == 2


# ---------------------------------------------------------------------------
# fpga_verify
# ---------------------------------------------------------------------------

def test_fpga_verify_empty_source_fails():
    ctx = _ctx({"source": ""})
    result = fpga_verify.fpga_verify(ctx)
    assert result["status"] == "failed"


def test_fpga_verify_simple_combinational():
    source = """
module and_gate(a, b, y);
  input a;
  input b;
  output y;
  assign y = a & b;
endmodule
"""
    ctx = _ctx({"source": source, "num_vectors": 4})
    result = fpga_verify.fpga_verify(ctx)
    assert result["status"] == "completed"
    assert result["result"]["module_name"] == "and_gate"
    assert result["result"]["test_vectors"] == 4
    assert result["metrics"]["inputs"] == 2
    assert result["metrics"]["outputs"] == 1


# ---------------------------------------------------------------------------
# myhdl_design
# ---------------------------------------------------------------------------

def test_myhdl_design_empty_source_fails():
    ctx = _ctx({"source": ""})
    result = myhdl_design.myhdl_design(ctx)
    assert result["status"] == "failed"


def test_myhdl_design_parses_signals():
    source = """
from myhdl import Signal, intbv

a = Signal(intbv(0)[8:])
b = Signal(intbv(0)[8:])
"""
    ctx = _ctx({"source": source, "module_name": "test_mod"})
    result = myhdl_design.myhdl_design(ctx)
    assert result["status"] == "completed"
    assert result["result"]["module_name"] == "test_mod"
    assert len(result["result"]["signals"]) >= 2
    assert result["result"]["verilog_stub"].startswith("module test_mod")


# ---------------------------------------------------------------------------
# riscv_cycle
# ---------------------------------------------------------------------------

def test_riscv_cycle_empty_instructions_fails():
    ctx = _ctx({"instructions": []})
    result = riscv_cycle.riscv_cycle(ctx)
    assert result["status"] == "failed"


def test_riscv_cycle_pipeline_trace():
    instructions = ["addi x1, x0, 1", "addi x2, x0, 2", "add x3, x1, x2"]
    ctx = _ctx({"instructions": instructions, "cycles": 10})
    result = riscv_cycle.riscv_cycle(ctx)
    assert result["status"] == "completed"
    assert len(result["result"]["trace"]) == 10
    assert result["result"]["stages"] == ["IF", "ID", "EX", "MEM", "WB"]


# ---------------------------------------------------------------------------
# data_viz_3d
# ---------------------------------------------------------------------------

def test_data_viz_3d_sphere():
    ctx = _ctx({"mesh_type": "sphere", "radius": 2.0})
    result = data_viz_3d.data_viz_3d(ctx)
    assert result["status"] == "completed"
    assert result["result"]["mesh_type"] == "sphere"
    assert result["result"]["vertex_count"] > 0
    assert result["result"]["face_count"] > 0
    verts = result["result"]["vertices"]
    assert len(verts) == result["result"]["vertex_count"]


def test_data_viz_3d_torus():
    ctx = _ctx({
        "mesh_type": "torus",
        "major_radius": 1.5,
        "minor_radius": 0.5,
    })
    result = data_viz_3d.data_viz_3d(ctx)
    assert result["status"] == "completed"
    assert result["result"]["mesh_type"] == "torus"
    assert result["result"]["vertex_count"] > 0
    assert result["result"]["face_count"] > 0


# ---------------------------------------------------------------------------
# stub_skills
# ---------------------------------------------------------------------------

def test_stub_skills_factory():
    stub = stub_skills._make_stub(
        "test_skill", "nonexistent_package_123"
    )
    assert callable(stub)
    assert stub.__name__ == "test_skill"


def test_stub_skill_returns_availability():
    ctx = _ctx({})
    stub = stub_skills._make_stub("optuna_tune", "optuna")
    result = stub(ctx)
    assert result["status"] == "completed"
    assert "available" in result["result"]
    assert "message" in result["result"]
