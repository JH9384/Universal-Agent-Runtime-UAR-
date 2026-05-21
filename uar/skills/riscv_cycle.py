"""Cycle-accurate RISC-V simulation skill.

A pipeline trace generator that models a simple 5-stage RISC-V
pipeline (IF, ID, EX, MEM, WB) and returns cycle-by-cycle state.
"""

from __future__ import annotations

from typing import Any, Dict, List

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext


class PipelineStage:
    """One pipeline stage entry."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.instr: str | None = None
        self.pc: int = 0
        self.stall: bool = False
        self.bubble: bool = False


def _simulate_pipeline(
    instructions: List[str], cycles: int
) -> List[Dict[str, Any]]:
    """Simulate a 5-stage pipeline for given instructions."""
    stages = ["IF", "ID", "EX", "MEM", "WB"]
    pipeline: List[PipelineStage] = [
        PipelineStage(s) for s in stages
    ]
    trace: List[Dict[str, Any]] = []
    pc = 0
    instr_idx = 0

    for cycle in range(cycles):
        # Move pipeline backward (WB -> MEM -> EX -> ID -> IF)
        for i in range(len(pipeline) - 1, 0, -1):
            pipeline[i].instr = pipeline[i - 1].instr
            pipeline[i].pc = pipeline[i - 1].pc
            pipeline[i].bubble = pipeline[i - 1].bubble

        # Fetch
        if instr_idx < len(instructions):
            pipeline[0].instr = instructions[instr_idx]
            pipeline[0].pc = pc
            pipeline[0].bubble = False
            pc += 4
            instr_idx += 1
        else:
            pipeline[0].instr = None
            pipeline[0].bubble = True

        trace.append({
            "cycle": cycle,
            "stages": [
                {
                    "stage": s.name,
                    "instr": s.instr,
                    "pc": s.pc,
                    "bubble": s.bubble,
                }
                for s in pipeline
            ],
            "pc": pc,
        })

    return trace


def riscv_cycle(ctx: PipelineContext) -> Dict[str, Any]:
    """Cycle-accurate RISC-V pipeline simulation.

    Parameters (from ctx.goal.metadata):
        instructions: list - Instruction mnemonics
        cycles: int - Number of cycles to simulate (default: 20)
    """
    params = ctx.goal.metadata or {}
    instructions = params.get("instructions", [])
    cycles = int(params.get("cycles", 20))

    if not instructions:
        return {
            "status": "failed",
            "error": "instructions required in metadata",
        }

    trace = _simulate_pipeline(instructions, cycles)

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "trace": trace,
            "instruction_count": len(instructions),
            "cycles": cycles,
            "stages": ["IF", "ID", "EX", "MEM", "WB"],
        },
        "metrics": {
            "instructions": len(instructions),
            "cycles": cycles,
            "trace_length": len(trace),
        },
    }


register_skill("riscv_cycle")(riscv_cycle)
