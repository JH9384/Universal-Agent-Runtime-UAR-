"""Unit tests for skills added in Batch 43-46 and core skills.

Covers: riscv_sim, verilog_parse, fpga_verify, myhdl_design,
riscv_cycle, data_viz_3d, stub_skills, section_sum, sum_review,
math_compute, cipher_ops, dependency_map.
"""

from __future__ import annotations

import pytest

from uar.core.contracts import PipelineContext, GoalSpec
from uar.skills import (
    riscv_sim,
    verilog_parse,
    fpga_verify,
    myhdl_design,
    riscv_cycle,
    data_viz_3d,
    stub_skills,
    trefoil_simulation,
    quantum_circuit_visualization,
    physics_compute,
    molecular_visualization,
    verilator_sim,
    micropython,
    platformio,
    cv_skills,
    ml_tools,
    stem_extended,
    section_sum,
    sum_review,
    math_compute,
    cipher_ops,
    dependency_map,
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


# ---------------------------------------------------------------------------
# trefoil_simulation
# ---------------------------------------------------------------------------

def test_trefoil_simulation_default():
    ctx = _ctx({})
    result = trefoil_simulation.trefoil_simulation(ctx)
    assert result["status"] == "completed"
    assert "knots" in result["result"]
    assert len(result["result"]["knots"]) == 3  # default num_trefoils
    assert result["result"]["equilibrium"] is True
    assert result["metrics"]["total_points"] == 256 * 3


def test_trefoil_simulation_custom_params():
    ctx = _ctx({
        "num_points": 64,
        "num_trefoils": 2,
        "expansion": 2.0,
        "twistor_strength": 0.5,
    })
    result = trefoil_simulation.trefoil_simulation(ctx)
    assert result["status"] == "completed"
    assert len(result["result"]["knots"]) == 2
    assert result["metrics"]["total_points"] == 64 * 2


def test_trefoil_simulation_keyframes():
    ctx = _ctx({"generate_keyframes": True, "num_keyframes": 10})
    result = trefoil_simulation.trefoil_simulation(ctx)
    assert result["status"] == "completed"
    assert len(result["result"]["keyframes"]) == 10


# ---------------------------------------------------------------------------
# quantum_circuit_visualization
# ---------------------------------------------------------------------------

def test_quantum_circuit_default():
    ctx = _ctx({"qubits": 4, "depth": 8})
    result = quantum_circuit_visualization.quantum_circuit_visualization(ctx)
    assert result["status"] == "completed"
    assert result["result"]["qubits"] == 4
    assert result["result"]["depth"] == 8
    assert result["result"]["gate_count"] > 0
    assert len(result["result"]["connections"]) > 0


def test_quantum_circuit_custom_gates():
    seq = [
        {"gate": "H", "targets": [0], "step": 0},
        {"gate": "CNOT", "targets": [1], "controls": [0], "step": 1},
    ]
    ctx = _ctx({"qubits": 2, "depth": 2, "gate_sequence": seq})
    result = quantum_circuit_visualization.quantum_circuit_visualization(ctx)
    assert result["status"] == "completed"
    gates = result["result"]["gates"]
    assert any(g["type"] == "H" for g in gates)
    assert any(g["type"] == "CNOT" for g in gates)
    assert any(g["type"] == "control" for g in gates)


# ---------------------------------------------------------------------------
# physics_compute
# ---------------------------------------------------------------------------

def test_physics_compute_missing_astropy():
    ctx = _ctx({
        "physics_operation": "convert",
        "physics_value": "1.0",
        "physics_from_unit": "m",
        "physics_to_unit": "km",
    })
    result = physics_compute.physics_compute(ctx)
    # Should either succeed with astropy or gracefully fail without it
    assert result["status"] in ("completed", "failed")
    if result["status"] == "failed":
        err = result["error"].lower()
        assert "astropy" in err or "not installed" in err


def test_physics_compute_missing_value():
    ctx = _ctx({"physics_operation": "convert"})
    result = physics_compute.physics_compute(ctx)
    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# molecular_visualization
# ---------------------------------------------------------------------------

def test_molecular_visualization_water():
    ctx = _ctx({"molecule": "water"})
    result = molecular_visualization.molecular_visualization(ctx)
    assert result["status"] == "completed"
    assert result["result"]["molecule"] == "water"
    assert result["result"]["atom_count"] == 3
    assert result["result"]["bond_count"] > 0
    # Check centered coordinates sum to ~0
    atoms = result["result"]["atoms"]
    cx = sum(a["x"] for a in atoms)
    cy = sum(a["y"] for a in atoms)
    cz = sum(a["z"] for a in atoms)
    assert abs(cx) < 0.01
    assert abs(cy) < 0.01
    assert abs(cz) < 0.01


def test_molecular_visualization_benzene():
    ctx = _ctx({"molecule": "benzene"})
    result = molecular_visualization.molecular_visualization(ctx)
    assert result["status"] == "completed"
    assert result["result"]["atom_count"] == 12


def test_molecular_visualization_protein():
    ctx = _ctx({"molecule": "protein", "residues": 5})
    result = molecular_visualization.molecular_visualization(ctx)
    assert result["status"] == "completed"
    assert result["result"]["atom_count"] == 20  # 4 atoms per residue


def test_molecular_visualization_unknown_defaults_to_water():
    ctx = _ctx({"molecule": "nonexistent"})
    result = molecular_visualization.molecular_visualization(ctx)
    assert result["status"] == "completed"
    assert result["result"]["molecule"] == "nonexistent"
    assert result["result"]["atom_count"] == 3  # falls back to water


# ---------------------------------------------------------------------------
# verilator_sim
# ---------------------------------------------------------------------------

def test_verilator_sim_no_source():
    ctx = _ctx({})
    result = verilator_sim.verilator_sim(ctx)
    assert result["status"] == "completed"
    assert "verilator" in result["result"]
    assert "available" in result["result"]["verilator"]


def test_verilator_sim_with_source():
    source = "module test(input a, output b); assign b = a; endmodule"
    ctx = _ctx({"source": source})
    result = verilator_sim.verilator_sim(ctx)
    assert result["status"] == "completed"
    assert "lint_issues" in result["result"]


def test_verilator_sim_bad_syntax():
    source = "module test(input a, output b); assign b = a;"
    ctx = _ctx({"source": source})
    result = verilator_sim.verilator_sim(ctx)
    assert result["status"] == "completed"
    # Lint issues only generated when verilator binary is available
    assert "lint_issues" in result["result"]


# ---------------------------------------------------------------------------
# micropython
# ---------------------------------------------------------------------------

def test_micropython_empty_code_fails():
    ctx = _ctx({"code": ""})
    result = micropython.micropython(ctx)
    assert result["status"] == "failed"


def test_micropython_pin_simulation():
    code = """
import machine
led = machine.Pin(2, machine.Pin.OUT)
led.value(1)
print("LED on")
"""
    ctx = _ctx({"code": code})
    result = micropython.micropython(ctx)
    assert result["status"] == "completed"
    # Pin init creates GPIO2 entry; .value() creates 'led' entry
    pins = result["result"]["pins"]
    assert "GPIO2" in pins
    assert pins["GPIO2"]["mode"] == "OUT"
    assert "led" in pins
    assert pins["led"]["value"] == 1
    assert result["metrics"]["pins"] == 2


# ---------------------------------------------------------------------------
# platformio
# ---------------------------------------------------------------------------

def test_platformio_default():
    ctx = _ctx({})
    result = platformio.platformio(ctx)
    assert result["status"] == "completed"
    assert result["result"]["board"] == "esp32dev"
    assert result["result"]["framework"] == "arduino"
    assert "platformio_available" in result["result"]
    assert "project_config" in result["result"]


def test_platformio_custom_board():
    ctx = _ctx({"board": "uno", "framework": "arduino"})
    result = platformio.platformio(ctx)
    assert result["status"] == "completed"
    assert result["result"]["board"] == "uno"


# ---------------------------------------------------------------------------
# cv_skills
# ---------------------------------------------------------------------------

def test_opencv_process_missing_dependency():
    ctx = _ctx({
        "cv_image_path": "/tmp/fake.jpg",
        "cv_operation": "grayscale",
    })
    result = cv_skills.opencv_process(ctx)
    # Will fail either due to missing cv2 or missing file
    assert result["status"] == "failed"


def test_yolo_detect_missing_dependency():
    ctx = _ctx({
        "cv_image_path": "/tmp/fake.jpg",
        "cv_conf": 0.5,
    })
    result = cv_skills.yolo_detect(ctx)
    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# ml_tools
# ---------------------------------------------------------------------------

def test_optuna_tune_missing_dependency():
    ctx = _ctx({
        "optuna_objective": "x**2",
        "optuna_n_trials": 10,
    })
    result = ml_tools.optuna_tune(ctx)
    assert result["status"] == "failed"
    assert "optuna" in result["error"].lower()


def test_chromadb_store_missing_dependency():
    ctx = _ctx({
        "chroma_operation": "query",
        "chroma_query": "test",
    })
    result = ml_tools.chromadb_store(ctx)
    assert result["status"] == "failed"
    assert "chromadb" in result["error"].lower()


# ---------------------------------------------------------------------------
# stem_extended
# ---------------------------------------------------------------------------

def test_scipy_opt_missing_dependency():
    ctx = _ctx({"opt_operation": "minimize"})
    result = stem_extended.scipy_opt(ctx)
    assert result["status"] == "failed"
    assert "scipy" in result["error"].lower()


def test_diff_eq_solve_missing_dependency():
    ctx = _ctx({"ode_function": "-y"})
    result = stem_extended.diff_eq_solve(ctx)
    assert result["status"] == "failed"
    assert "scipy" in result["error"].lower()


def test_quantum_circuit_missing_dependency():
    ctx = _ctx({"qc_gates": ["H", "CNOT"]})
    result = stem_extended.quantum_circuit(ctx)
    assert result["status"] == "failed"
    assert "qiskit" in result["error"].lower()


def test_chem_analysis_missing_dependency():
    ctx = _ctx({"smiles": "CCO"})
    result = stem_extended.chem_analysis(ctx)
    assert result["status"] == "failed"
    assert "rdkit" in result["error"].lower()


def test_bio_compute_missing_dependency():
    ctx = _ctx({"sequence": "ATCG"})
    result = stem_extended.bio_compute(ctx)
    assert result["status"] == "failed"
    assert "biopython" in result["error"].lower()


def test_relativity_missing_dependency():
    ctx = _ctx({"rel_metric": "schwarzschild"})
    result = stem_extended.relativity(ctx)
    assert result["status"] == "failed"
    assert "sympy" in result["error"].lower()


# ---------------------------------------------------------------------------
# section_sum
# ---------------------------------------------------------------------------

def test_section_sum_returns_summary():
    ctx = _ctx({})
    result = section_sum.section_sum(ctx)
    assert "summary" in result
    assert "Processed goal: test" in result["summary"]


# ---------------------------------------------------------------------------
# sum_review
# ---------------------------------------------------------------------------

def test_sum_review_with_data():
    goal = GoalSpec(
        id="test-id",
        user_intent="test",
        objective="test",
        metadata={},
    )
    ctx = PipelineContext(goal=goal, data={"doc_ingest": {"documents": []}})
    ctx.emit("skill_complete", {"skill": "doc_ingest"})
    result = sum_review.sum_review(ctx)
    assert "skills_executed" in result
    assert "doc_ingest" in result["skills_executed"]
    assert result["events_count"] == 1


def test_sum_review_empty():
    ctx = _ctx({})
    result = sum_review.sum_review(ctx)
    assert result["skills_executed"] == []
    assert result["events_count"] == 0


# ---------------------------------------------------------------------------
# math_compute
# ---------------------------------------------------------------------------

def test_math_compute_missing_sympy():
    import importlib.util

    if importlib.util.find_spec("sympy") is not None:
        pytest.skip("sympy is installed; skipping missing-dep test")
    ctx = _ctx({"math_operation": "evaluate", "math_expression": "x + 1"})
    result = math_compute.math_compute(ctx)
    assert result["status"] == "failed"
    assert "sympy" in result["error"].lower()


def test_math_compute_missing_expression():
    import importlib.util

    if importlib.util.find_spec("sympy") is None:
        pytest.skip("sympy not installed")
    ctx = _ctx({"math_operation": "evaluate"})
    result = math_compute.math_compute(ctx)
    assert result["status"] == "failed"
    assert "math_expression is required" in result["error"]


def test_math_compute_evaluate():
    import importlib.util

    if importlib.util.find_spec("sympy") is None:
        pytest.skip("sympy not installed")
    ctx = _ctx({"math_operation": "evaluate", "math_expression": "2 + 2"})
    result = math_compute.math_compute(ctx)
    assert result["status"] == "completed"
    assert "result" in result


# ---------------------------------------------------------------------------
# cipher_ops
# ---------------------------------------------------------------------------

def test_cipher_ops_missing_pycryptodome():
    import importlib.util

    if importlib.util.find_spec("Crypto") is not None:
        pytest.skip("pycryptodome is installed; skipping missing-dep test")
    ctx = _ctx({"cipher_operation": "hash", "cipher_data": "dGVzdA=="})
    result = cipher_ops.cipher_ops(ctx)
    assert result["status"] == "failed"
    assert "pycryptodome" in result["error"].lower()


def test_cipher_ops_missing_data():
    import importlib.util

    if importlib.util.find_spec("Crypto") is None:
        pytest.skip("pycryptodome not installed")
    ctx = _ctx({"cipher_operation": "hash"})
    result = cipher_ops.cipher_ops(ctx)
    assert result["status"] == "failed"
    assert "cipher_data is required" in result["error"]


def test_cipher_ops_hash():
    import importlib.util

    if importlib.util.find_spec("Crypto") is None:
        pytest.skip("pycryptodome not installed")
    ctx = _ctx({
        "cipher_operation": "hash",
        "cipher_algorithm": "SHA256",
        "cipher_data": "dGVzdA==",  # base64("test")
    })
    result = cipher_ops.cipher_ops(ctx)
    assert result["status"] == "completed"
    assert "hash" in result


# ---------------------------------------------------------------------------
# dependency_map
# ---------------------------------------------------------------------------

def test_dependency_map_empty():
    ctx = _ctx({})
    result = dependency_map.dependency_map(ctx)
    assert result["node_count"] == 0
    assert result["edge_count"] == 0


def test_dependency_map_with_imports():
    goal = GoalSpec(
        id="test-id",
        user_intent="test",
        objective="test",
        metadata={},
    )
    ctx = PipelineContext(
        goal=goal,
        data={
            "doc_ingest": {
                "documents": [
                    {
                        "path": "/tmp/a.py",
                        "text": "import os\nfrom sys import path",
                    },
                    {
                        "path": "/tmp/b.py",
                        "text": "import json",
                    },
                ]
            }
        },
    )
    result = dependency_map.dependency_map(ctx)
    assert result["node_count"] == 5  # 2 files + 3 imports
    assert result["edge_count"] == 3
    assert any(n["id"] == "/tmp/a.py" for n in result["nodes"])
    assert any(e["from"] == "/tmp/a.py" for e in result["edges"])
