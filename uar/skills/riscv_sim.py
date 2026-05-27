"""RISC-V simulation skill.

A lightweight RV32I emulator for executing RISC-V assembly and
returning register state, memory contents, and execution trace.
No external dependencies — pure Python implementation.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext

logger = logging.getLogger(__name__)


# RV32I opcodes
def _sign_extend(val: int, bits: int) -> int:
    """Sign-extend a value to 32 bits."""
    if val & (1 << (bits - 1)):
        return val - (1 << bits)
    return val


class RiscvEmulator:
    """Minimal RV32I emulator."""

    def __init__(self, memory_size: int = 4096):
        self.pc: int = 0
        self.registers: List[int] = [0] * 32
        self.memory: bytearray = bytearray(memory_size)
        self.trace: List[Dict[str, Any]] = []
        self.instruction_count: int = 0
        self.max_instructions: int = 10000

        # Register names
        self.reg_names = [
            "zero", "ra", "sp", "gp", "tp", "t0", "t1", "t2",
            "s0", "s1", "a0", "a1", "a2", "a3", "a4", "a5",
            "a6", "a7", "s2", "s3", "s4", "s5", "s6", "s7",
            "s8", "s9", "s10", "s11", "t3", "t4", "t5", "t6",
        ]

    def load_program(self, words: List[int], start_addr: int = 0) -> None:
        """Load program words into memory."""
        for i, word in enumerate(words):
            addr = start_addr + i * 4
            self.memory[addr:addr + 4] = word.to_bytes(4, "little")
        self.pc = start_addr

    def read_word(self, addr: int) -> int:
        """Read 32-bit word from memory."""
        return int.from_bytes(self.memory[addr:addr + 4], "little")

    def write_word(self, addr: int, val: int) -> None:
        """Write 32-bit word to memory."""
        self.memory[addr:addr + 4] = (val & 0xFFFFFFFF).to_bytes(4, "little")

    def step(self) -> bool:
        """Execute one instruction. Returns False on halt/error."""
        if self.instruction_count >= self.max_instructions:
            return False

        instr = self.read_word(self.pc)
        self.instruction_count += 1

        # Decode fields
        opcode = instr & 0x7F
        rd = (instr >> 7) & 0x1F
        rs1 = (instr >> 15) & 0x1F
        rs2 = (instr >> 20) & 0x1F
        funct3 = (instr >> 12) & 0x7
        funct7 = (instr >> 25) & 0x7F

        # I-type immediate
        imm_i = _sign_extend((instr >> 20) & 0xFFF, 12)
        # S-type immediate
        imm_s = _sign_extend(
            ((instr >> 25) << 5) | ((instr >> 7) & 0x1F), 12
        )
        # B-type immediate
        imm_b = _sign_extend(
            ((instr >> 31) << 12)
            | (((instr >> 7) & 1) << 11)
            | (((instr >> 25) & 0x3F) << 5)
            | (((instr >> 8) & 0xF) << 1),
            13,
        )
        # U-type immediate
        imm_u = instr & 0xFFFFF000
        # J-type immediate
        imm_j = _sign_extend(
            ((instr >> 31) << 20)
            | (((instr >> 12) & 0xFF) << 12)
            | (((instr >> 20) & 1) << 11)
            | (((instr >> 21) & 0x3FF) << 1),
            21,
        )

        old_pc = self.pc

        # R-type
        if opcode == 0b0110011:
            a = self.registers[rs1]
            b = self.registers[rs2]
            if funct3 == 0x0 and funct7 == 0x00:
                self.registers[rd] = (a + b) & 0xFFFFFFFF
            elif funct3 == 0x0 and funct7 == 0x20:
                self.registers[rd] = (a - b) & 0xFFFFFFFF
            elif funct3 == 0x1 and funct7 == 0x00:
                self.registers[rd] = (a << (b & 0x1F)) & 0xFFFFFFFF
            if funct3 == 0x2 and funct7 == 0x00:
                self.registers[rd] = (
                    1 if (a & 0xFFFFFFFF) < (b & 0xFFFFFFFF) else 0
                )
            elif funct3 == 0x3 and funct7 == 0x00:
                self.registers[rd] = 1 if a < b else 0
            elif funct3 == 0x4 and funct7 == 0x00:
                self.registers[rd] = a ^ b
            elif funct3 == 0x5 and funct7 == 0x00:
                self.registers[rd] = (a >> (b & 0x1F)) & 0xFFFFFFFF
            elif funct3 == 0x5 and funct7 == 0x20:
                self.registers[rd] = (
                    (_sign_extend(a, 32) >> (b & 0x1F)) & 0xFFFFFFFF
                )
            elif funct3 == 0x6 and funct7 == 0x00:
                self.registers[rd] = a | b
            elif funct3 == 0x7 and funct7 == 0x00:
                self.registers[rd] = a & b
            self.pc += 4

        # I-type ALU
        elif opcode == 0b0010011:
            a = self.registers[rs1]
            if funct3 == 0x0:
                self.registers[rd] = (a + imm_i) & 0xFFFFFFFF
            elif funct3 == 0x1 and funct7 == 0x00:
                self.registers[rd] = (a << (imm_i & 0x1F)) & 0xFFFFFFFF
            elif funct3 == 0x2:
                self.registers[rd] = 1 if (_sign_extend(a, 32) < imm_i) else 0
            elif funct3 == 0x4:
                self.registers[rd] = a ^ imm_i
            elif funct3 == 0x5 and funct7 == 0x00:
                self.registers[rd] = (a >> (imm_i & 0x1F)) & 0xFFFFFFFF
            elif funct3 == 0x5 and funct7 == 0x20:
                self.registers[rd] = (
                    (_sign_extend(a, 32) >> (imm_i & 0x1F)) & 0xFFFFFFFF
                )
            elif funct3 == 0x6:
                self.registers[rd] = a | imm_i
            elif funct3 == 0x7:
                self.registers[rd] = a & imm_i
            self.pc += 4

        # Load
        elif opcode == 0b0000011:
            addr = (self.registers[rs1] + imm_i) & 0xFFFFFFFF
            if funct3 == 0x0:  # LB
                self.registers[rd] = _sign_extend(self.memory[addr], 8)
            elif funct3 == 0x1:  # LH
                val = int.from_bytes(self.memory[addr:addr + 2], "little")
                self.registers[rd] = _sign_extend(val, 16)
            elif funct3 == 0x2:  # LW
                self.registers[rd] = self.read_word(addr)
            if funct3 == 0x4:  # LBU
                self.registers[rd] = self.memory[addr]
            elif funct3 == 0x5:  # LHU
                val = int.from_bytes(
                    self.memory[addr:addr + 2], "little"
                )
                self.registers[rd] = val
            self.pc += 4

        # Store
        elif opcode == 0b0100011:
            addr = (self.registers[rs1] + imm_s) & 0xFFFFFFFF
            val = self.registers[rs2]
            if funct3 == 0x0:  # SB
                self.memory[addr] = val & 0xFF
            elif funct3 == 0x1:  # SH
                ba = (val & 0xFFFF).to_bytes(2, "little")
                self.memory[addr:addr + 2] = ba
            elif funct3 == 0x2:  # SW
                self.write_word(addr, val)
            self.pc += 4

        # Branch
        elif opcode == 0b1100011:
            a = self.registers[rs1]
            b = self.registers[rs2]
            take = False
            if funct3 == 0x0:
                take = a == b
            elif funct3 == 0x1:
                take = a != b
            elif funct3 == 0x4:
                take = _sign_extend(a, 32) < _sign_extend(b, 32)
            elif funct3 == 0x5:
                take = _sign_extend(a, 32) >= _sign_extend(b, 32)
            elif funct3 == 0x6:
                take = (a & 0xFFFFFFFF) < (b & 0xFFFFFFFF)
            elif funct3 == 0x7:
                take = (a & 0xFFFFFFFF) >= (b & 0xFFFFFFFF)
            if take:
                self.pc += imm_b
            else:
                self.pc += 4

        # JAL
        elif opcode == 0b1101111:
            self.registers[rd] = (self.pc + 4) & 0xFFFFFFFF
            self.pc += imm_j

        # JALR
        elif opcode == 0b1100111 and funct3 == 0x0:
            self.registers[rd] = (self.pc + 4) & 0xFFFFFFFF
            self.pc = (self.registers[rs1] + imm_i) & ~1

        # LUI
        elif opcode == 0b0110111:
            self.registers[rd] = imm_u & 0xFFFFFFFF
            self.pc += 4

        # AUIPC
        elif opcode == 0b0010111:
            self.registers[rd] = (self.pc + imm_u) & 0xFFFFFFFF
            self.pc += 4

        # ECALL / EBREAK
        elif opcode == 0b1110011:
            return False  # Halt

        else:
            # Unknown opcode — skip
            self.pc += 4

        self.registers[0] = 0  # x0 always zero

        self.trace.append({
            "pc": old_pc,
            "instr": f"0x{instr:08x}",
            "opcode": f"0x{opcode:02x}",
            "rd": rd if opcode not in (0b0100011, 0b1100011) else None,
            "rs1": rs1,
            "rs2": rs2,
            "registers": list(self.registers),
        })

        return True

    def run(self, max_steps: int = 10000) -> None:
        """Run until halt or max steps."""
        self.max_instructions = max_steps
        while self.step():
            pass


def _parse_assembly(asm: str) -> List[int]:
    """Parse a tiny subset of RISC-V assembly to machine code.

    Supports basic RV32I instructions with register names.
    """
    reg_map = {
        "zero": 0, "ra": 1, "sp": 2, "gp": 3, "tp": 4,
        "t0": 5, "t1": 6, "t2": 7,
        "s0": 8, "s1": 9,
        "a0": 10, "a1": 11, "a2": 12, "a3": 13, "a4": 14, "a5": 15,
        "a6": 16, "a7": 17,
        "s2": 18, "s3": 19, "s4": 20, "s5": 21, "s6": 22, "s7": 23,
        "s8": 24, "s9": 25, "s10": 26, "s11": 27,
        "t3": 28, "t4": 29, "t5": 30, "t6": 31,
    }
    for i in range(32):
        reg_map[f"x{i}"] = i

    words: List[int] = []
    labels: Dict[str, int] = {}

    # First pass: collect labels
    addr = 0
    for line in asm.strip().splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        if ":" in line.split()[0]:
            labels[line.split(":")[0]] = addr
            rest = line.split(":", 1)[1].strip()
            if not rest:
                continue
        addr += 4

    # Second pass: encode
    addr = 0
    for line in asm.strip().splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        if ":" in line.split()[0]:
            rest = line.split(":", 1)[1].strip()
            if not rest:
                continue
            line = rest

        parts = re.split(r"[,\s()]+", line.strip())
        parts = [p for p in parts if p]
        if not parts:
            continue

        op = parts[0].lower()
        word = 0

        def _enc_r(f7: int, f3: int, opc: int) -> int:
            return (
                (f7 << 25)
                | (reg_map.get(parts[3], 0) << 20)
                | (f3 << 12)
                | (reg_map.get(parts[1], 0) << 7)
                | opc
            )

        def _enc_i(imm: int, f3: int, opc: int) -> int:
            return (
                ((imm & 0xFFF) << 20)
                | (reg_map.get(parts[2], 0) << 15)
                | (f3 << 12)
                | (reg_map.get(parts[1], 0) << 7)
                | opc
            )

        def _enc_s(imm: int, f3: int, opc: int) -> int:
            rs2 = reg_map.get(parts[1], 0)
            rs1_v = reg_map.get(parts[3], 0)
            return (
                ((imm & 0xFE0) << 20)
                | (rs2 << 20)
                | (f3 << 12)
                | (rs1_v << 15)
                | ((imm & 0x1F) << 7)
                | opc
            )

        def _enc_b(imm: int, f3: int, opc: int) -> int:
            imm13 = imm
            return (
                (((imm13 >> 12) & 1) << 31)
                | (((imm13 >> 5) & 0x3F) << 25)
                | (reg_map.get(parts[2], 0) << 20)
                | (f3 << 12)
                | (reg_map.get(parts[1], 0) << 15)
                | (((imm13 >> 1) & 0xF) << 8)
                | (((imm13 >> 11) & 1) << 7)
                | opc
            )

        def _enc_u(imm: int, opc: int) -> int:
            return (
                (imm & 0xFFFFF000)
                | (reg_map.get(parts[1], 0) << 7)
                | opc
            )

        def _enc_j(label: str, opc: int) -> int:
            tgt = labels.get(label, addr)
            imm21 = tgt - addr
            return (
                (((imm21 >> 20) & 1) << 31)
                | (((imm21 >> 1) & 0x3FF) << 21)
                | (((imm21 >> 11) & 1) << 20)
                | (((imm21 >> 12) & 0xFF) << 12)
                | (reg_map.get(parts[1], 0) << 7)
                | opc
            )

        try:
            if op == "add":
                word = _enc_r(0x00, 0x0, 0x33)
            elif op == "sub":
                word = _enc_r(0x20, 0x0, 0x33)
            elif op == "and":
                word = _enc_r(0x00, 0x7, 0x33)
            elif op == "or":
                word = _enc_r(0x00, 0x6, 0x33)
            elif op == "xor":
                word = _enc_r(0x00, 0x4, 0x33)
            elif op == "sll":
                word = _enc_r(0x00, 0x1, 0x33)
            elif op == "srl":
                word = _enc_r(0x00, 0x5, 0x33)
            elif op == "sra":
                word = _enc_r(0x20, 0x5, 0x33)
            elif op == "slt":
                word = _enc_r(0x00, 0x2, 0x33)
            elif op == "sltu":
                word = _enc_r(0x00, 0x3, 0x33)
            elif op == "addi":
                word = _enc_i(int(parts[3]), 0x0, 0x13)
            elif op == "andi":
                word = _enc_i(int(parts[3]), 0x7, 0x13)
            elif op == "ori":
                word = _enc_i(int(parts[3]), 0x6, 0x13)
            elif op == "xori":
                word = _enc_i(int(parts[3]), 0x4, 0x13)
            elif op == "slli":
                word = _enc_i(int(parts[3]) & 0x1F, 0x1, 0x13)
            elif op == "srli":
                word = _enc_i(int(parts[3]) & 0x1F, 0x5, 0x13)
            elif op == "srai":
                word = _enc_i(0x400 | (int(parts[3]) & 0x1F), 0x5, 0x13)
            elif op == "slti":
                word = _enc_i(int(parts[3]), 0x2, 0x13)
            elif op == "sltiu":
                word = _enc_i(int(parts[3]), 0x3, 0x13)
            elif op == "lw":
                word = _enc_i(int(parts[2]), 0x2, 0x03)
            elif op == "lh":
                word = _enc_i(int(parts[2]), 0x1, 0x03)
            elif op == "lb":
                word = _enc_i(int(parts[2]), 0x0, 0x03)
            elif op == "lhu":
                word = _enc_i(int(parts[2]), 0x5, 0x03)
            elif op == "lbu":
                word = _enc_i(int(parts[2]), 0x4, 0x03)
            elif op == "sw":
                word = _enc_s(int(parts[2]), 0x2, 0x23)
            elif op == "sh":
                word = _enc_s(int(parts[2]), 0x1, 0x23)
            elif op == "sb":
                word = _enc_s(int(parts[2]), 0x0, 0x23)
            elif op == "beq":
                tgt = labels.get(parts[3], addr) - addr
                word = _enc_b(tgt, 0x0, 0x63)
            elif op == "bne":
                tgt = labels.get(parts[3], addr) - addr
                word = _enc_b(tgt, 0x1, 0x63)
            elif op == "blt":
                tgt = labels.get(parts[3], addr) - addr
                word = _enc_b(tgt, 0x4, 0x63)
            elif op == "bge":
                tgt = labels.get(parts[3], addr) - addr
                word = _enc_b(tgt, 0x5, 0x63)
            elif op == "bltu":
                tgt = labels.get(parts[3], addr) - addr
                word = _enc_b(tgt, 0x6, 0x63)
            elif op == "bgeu":
                tgt = labels.get(parts[3], addr) - addr
                word = _enc_b(tgt, 0x7, 0x63)
            elif op == "jal":
                word = _enc_j(parts[2], 0x6F)
            elif op == "jalr":
                word = _enc_i(int(parts[3]), 0x0, 0x67)
            elif op == "lui":
                word = _enc_u(int(parts[2], 0), 0x37)
            elif op == "auipc":
                word = _enc_u(int(parts[2], 0), 0x17)
            elif op == "ecall":
                word = 0x00000073
            elif op == "ebreak":
                word = 0x00100073
            else:
                word = 0x00000013  # NOP
        except (IndexError, ValueError):
            word = 0x00000013  # NOP

        words.append(word & 0xFFFFFFFF)
        addr += 4

    return words


def riscv_simulation(ctx: PipelineContext) -> Dict[str, Any]:
    """Run RISC-V assembly simulation.

    Parameters (from ctx.goal.metadata):
        assembly: str - RISC-V assembly code
        memory_size: int - Memory size in bytes (default: 4096)
        max_steps: int - Max instructions to execute (default: 10000)
    """
    params = ctx.goal.metadata or {}
    assembly = str(params.get("assembly", ""))
    memory_size = int(params.get("memory_size", 4096))
    max_steps = int(params.get("max_steps", 10000))

    if not assembly.strip():
        return {
            "status": "failed",
            "error": "assembly is required in goal metadata",
        }

    try:
        words = _parse_assembly(assembly)
        emu = RiscvEmulator(memory_size=memory_size)
        emu.load_program(words)
        emu.run(max_steps=max_steps)

        # Build register output
        registers = []
        for i, val in enumerate(emu.registers):
            registers.append({
                "index": i,
                "name": emu.reg_names[i],
                "value": val,
                "hex": f"0x{val:08x}",
            })

        # Memory dump (first 256 bytes)
        mem_dump = []
        for addr in range(0, min(256, memory_size), 4):
            w = int.from_bytes(emu.memory[addr:addr + 4], "little")
            mem_dump.append({
                "addr": addr,
                "hex": f"0x{w:08x}",
            })

        # Final trace (last 50 entries to avoid bloat)
        trace = emu.trace[-50:] if len(emu.trace) > 50 else emu.trace

        return {
            "status": "completed",
            "goal": ctx.goal.user_intent,
            "result": {
                "registers": registers,
                "memory": mem_dump,
                "trace": trace,
                "instruction_count": emu.instruction_count,
                "final_pc": emu.pc,
            },
            "metrics": {
                "instructions_executed": emu.instruction_count,
                "trace_length": len(emu.trace),
                "memory_size": memory_size,
            },
        }
    except Exception:
        logger.exception("riscv_sim failed")
        return {
            "status": "failed",
            "error": "RISC-V simulation failed",
        }


register_skill("riscv_sim")(riscv_simulation)
