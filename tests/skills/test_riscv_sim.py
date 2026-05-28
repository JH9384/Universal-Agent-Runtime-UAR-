"""Tests for RISC-V simulation skill.

Covers RiscvEmulator, _parse_assembly, _sign_extend, riscv_simulation.
"""

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.riscv_sim import (
    _sign_extend,
    RiscvEmulator,
    _parse_assembly,
    riscv_simulation,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="test", objective="t", metadata=meta
        )
    )


class TestSignExtend:
    """Sign extension helper."""

    def test_positive(self):
        assert _sign_extend(0x000, 12) == 0
        assert _sign_extend(0x7FF, 12) == 2047

    def test_negative(self):
        assert _sign_extend(0xFFF, 12) == -1
        assert _sign_extend(0x800, 12) == -2048


class TestRiscvEmulatorInit:
    """Emulator initialization."""

    def test_defaults(self):
        emu = RiscvEmulator()
        assert emu.pc == 0
        assert len(emu.registers) == 32
        assert all(r == 0 for r in emu.registers)
        assert len(emu.memory) == 4096
        assert emu.trace == []
        assert emu.instruction_count == 0

    def test_custom_memory(self):
        emu = RiscvEmulator(memory_size=8192)
        assert len(emu.memory) == 8192


class TestMemoryOps:
    """Memory read/write."""

    def test_read_write_word(self):
        emu = RiscvEmulator()
        emu.write_word(0, 0xDEADBEEF)
        assert emu.read_word(0) == 0xDEADBEEF

    def test_load_program(self):
        emu = RiscvEmulator()
        emu.load_program([0x12345678, 0xAABBCCDD])
        assert emu.read_word(0) == 0x12345678
        assert emu.read_word(4) == 0xAABBCCDD
        assert emu.pc == 0


class TestStepInstructions:
    """Execute individual instruction types."""

    def test_add(self):
        emu = RiscvEmulator()
        # add x3, x1, x2  (R-type: rd=3, rs1=1, rs2=2)
        instr = (
            (0x00 << 25) | (2 << 20) | (0x0 << 12) | (1 << 15)
            | (3 << 7) | 0x33
        )
        emu.write_word(0, instr)
        emu.registers[1] = 5
        emu.registers[2] = 7
        emu.step()
        assert emu.registers[3] == 12
        assert emu.registers[0] == 0  # x0 stays zero

    def test_addi(self):
        emu = RiscvEmulator()
        # addi x1, x0, 42  (I-type)
        instr = (
            (42 << 20) | (0 << 15) | (0x0 << 12) | (1 << 7) | 0x13
        )
        emu.write_word(0, instr)
        emu.step()
        assert emu.registers[1] == 42

    def test_lui(self):
        emu = RiscvEmulator()
        # lui x1, 0x12345  (U-type)
        instr = (0x12345 << 12) | (1 << 7) | 0x37
        emu.write_word(0, instr)
        emu.step()
        assert emu.registers[1] == 0x12345000

    def test_ecall_halt(self):
        emu = RiscvEmulator()
        emu.write_word(0, 0x00000073)  # ECALL
        result = emu.step()
        assert result is False

    def test_unknown_opcode(self):
        emu = RiscvEmulator()
        emu.write_word(0, 0xFFFFFFFF)  # Invalid
        emu.step()
        assert emu.pc == 4

    def test_max_instructions(self):
        emu = RiscvEmulator()
        emu.instruction_count = 10000
        emu.max_instructions = 10000
        result = emu.step()
        assert result is False


class TestBranchInstructions:
    """Branch and jump instructions."""

    def test_beq_taken(self):
        emu = RiscvEmulator()
        # beq x1, x2, offset (B-type)
        emu.registers[1] = 5
        emu.registers[2] = 5
        # beq x1, x2, 8 -> opcode=0x63, funct3=0x0
        # imm = 8, encoded as B-type
        imm = 8
        instr = (
            (((imm >> 12) & 1) << 31)
            | (((imm >> 5) & 0x3F) << 25)
            | (2 << 20)
            | (0x0 << 12)
            | (1 << 15)
            | (((imm >> 1) & 0xF) << 8)
            | (((imm >> 11) & 1) << 7)
            | 0x63
        )
        emu.write_word(0, instr)
        emu.step()
        assert emu.pc == 8  # branched forward 8 bytes (PC=0 + 8)

    def test_jal(self):
        emu = RiscvEmulator()
        # jal x1, 16 (J-type: rd=1, imm=16)
        imm = 16
        instr = (
            (((imm >> 20) & 1) << 31)
            | (((imm >> 1) & 0x3FF) << 21)
            | (((imm >> 11) & 1) << 20)
            | (((imm >> 12) & 0xFF) << 12)
            | (1 << 7)
            | 0x6F
        )
        emu.write_word(0, instr)
        emu.step()
        assert emu.registers[1] == 4  # return address
        assert emu.pc == 16


class TestRun:
    """Run multiple instructions."""

    def test_run_until_halt(self):
        emu = RiscvEmulator()
        # addi x1, x0, 1; addi x2, x0, 2; ecall
        prog = [
            (1 << 20) | (0 << 15) | (0x0 << 12) | (1 << 7) | 0x13,
            (2 << 20) | (0 << 15) | (0x0 << 12) | (2 << 7) | 0x13,
            0x00000073,  # ECALL
        ]
        emu.load_program(prog)
        emu.run()
        assert emu.registers[1] == 1
        assert emu.registers[2] == 2
        assert emu.instruction_count == 3


class TestParseAssembly:
    """Assembly parser."""

    def test_add(self):
        words = _parse_assembly("add x3, x1, x2")
        assert len(words) == 1
        opcode = words[0] & 0x7F
        assert opcode == 0x33

    def test_addi(self):
        words = _parse_assembly("addi x1, x0, 42")
        assert len(words) == 1

    def test_lw(self):
        words = _parse_assembly("lw x1, 0(x0)")
        assert len(words) == 1

    def test_sw(self):
        words = _parse_assembly("sw x1, 0(x0)")
        assert len(words) == 1

    def test_beq(self):
        words = _parse_assembly("beq x1, x2, loop\nloop:")
        assert len(words) == 1

    def test_empty_and_comments(self):
        words = _parse_assembly("# comment\n\nadd x1, x0, x0")
        assert len(words) == 1

    def test_label_only(self):
        words = _parse_assembly("start:\nadd x1, x0, x0")
        assert len(words) == 1

    def test_ecall(self):
        words = _parse_assembly("ecall")
        assert words[0] == 0x00000073

    def test_ebreak(self):
        words = _parse_assembly("ebreak")
        assert words[0] == 0x00100073

    def test_unknown_op_becomes_nop(self):
        words = _parse_assembly("unknown_op x1, x2")
        assert words[0] == 0x00000013  # NOP


class TestRiscvSimulation:
    """Skill entry point."""

    def test_empty_assembly(self):
        result = riscv_simulation(_ctx({"assembly": ""}))
        assert result["status"] == "failed"
        assert "assembly is required" in result["error"].lower()

    def test_simple_program(self):
        result = riscv_simulation(
            _ctx({"assembly": "addi x1, x0, 5\naddi x2, x0, 3\necall"})
        )
        assert result["status"] == "completed"
        assert result["result"]["instruction_count"] == 3
        regs = result["result"]["registers"]
        assert regs[1]["value"] == 5
        assert regs[2]["value"] == 3

    def test_memory_size_param(self):
        result = riscv_simulation(
            _ctx({
                "assembly": "addi x1, x0, 1\necall",
                "memory_size": 2048,
            })
        )
        assert result["status"] == "completed"
        assert result["metrics"]["memory_size"] == 2048

    def test_trace_truncation(self):
        asm = "\n".join(["addi x1, x0, 1"] * 100) + "\necall"
        result = riscv_simulation(_ctx({"assembly": asm}))
        assert result["status"] == "completed"
        trace = result["result"]["trace"]
        assert len(trace) <= 50
