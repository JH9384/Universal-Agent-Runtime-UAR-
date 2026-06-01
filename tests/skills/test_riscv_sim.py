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


# ---------------------------------------------------------------------------
# Regression: encoding bug fixes
# ---------------------------------------------------------------------------

class TestEncRRegressions:
    """Bug 2 regression: _enc_r was missing rs1 — R-type always had rs1=0.

    The RV32I R-type layout (from spec):
        [31:25] funct7 | [24:20] rs2 | [19:15] rs1 | [14:12] funct3
        | [11:7] rd | [6:0] opcode
    """

    def test_add_rs1_encoded_correctly(self):
        """add x3, x1, x2 — rs1=x1 must appear at bits [19:15]."""
        words = _parse_assembly("add x3, x1, x2")
        assert len(words) == 1
        word = words[0]
        rd = (word >> 7) & 0x1F
        rs1 = (word >> 15) & 0x1F
        rs2 = (word >> 20) & 0x1F
        funct7 = (word >> 25) & 0x7F
        assert rd == 3, f"rd should be 3, got {rd}"
        assert rs1 == 1, f"rs1 should be 1 (x1), got {rs1} — Bug 2 regression"
        assert rs2 == 2, f"rs2 should be 2 (x2), got {rs2}"
        assert funct7 == 0x00

    def test_sub_rs1_rs2_distinct(self):
        """sub x5, x3, x4 — rs1=x3 and rs2=x4 must be in distinct fields."""
        words = _parse_assembly("sub x5, x3, x4")
        assert len(words) == 1
        word = words[0]
        rd = (word >> 7) & 0x1F
        rs1 = (word >> 15) & 0x1F
        rs2 = (word >> 20) & 0x1F
        funct7 = (word >> 25) & 0x7F
        assert rd == 5
        assert rs1 == 3, f"rs1 must be 3, got {rs1}"
        assert rs2 == 4, f"rs2 must be 4, got {rs2}"
        assert funct7 == 0x20

    def test_add_round_trip_via_emulator(self):
        """Assemble 'add x3, x1, x2' and verify the emulator produces 12."""
        words = _parse_assembly("add x3, x1, x2\necall")
        emu = RiscvEmulator()
        emu.load_program(words)
        emu.registers[1] = 5
        emu.registers[2] = 7
        emu.run()
        assert emu.registers[3] == 12, (
            f"Expected x3=12 from add x3, x1, x2 with x1=5 x2=7, "
            f"got {emu.registers[3]}. rs1 encoding bug regression."
        )

    def test_and_uses_rs1_not_zero(self):
        """and x2, x1, x3 — result must use x1 (rs1), not zero."""
        words = _parse_assembly("and x2, x1, x3\necall")
        emu = RiscvEmulator()
        emu.load_program(words)
        emu.registers[1] = 0b1111
        emu.registers[3] = 0b1010
        emu.run()
        assert emu.registers[2] == 0b1010, (
            f"Expected 0b1010, got {emu.registers[2]:#b}. "
            "rs1 was not encoded — used x0 instead of x1."
        )


class TestEncSRegressions:
    """Bug 6 regression: _enc_s had imm[11:5] and rs2 both at <<20.

    The RV32I S-type layout (from spec):
        [31:25] imm[11:5] | [24:20] rs2 | [19:15] rs1
        | [14:12] funct3 | [11:7] imm[4:0] | [6:0] opcode
    """

    def test_sw_imm_upper_bits_at_31_25(self):
        """sw x2, 64(x1) — imm=64 (0x40), upper bits at [31:25]."""
        words = _parse_assembly("sw x2, 64(x1)")
        assert len(words) == 1
        word = words[0]
        imm_upper = (word >> 25) & 0x7F   # bits [31:25]
        imm_lower = (word >> 7) & 0x1F    # bits [11:7]
        imm = (imm_upper << 5) | imm_lower
        rs1 = (word >> 15) & 0x1F
        rs2 = (word >> 20) & 0x1F
        assert imm == 64, (
            f"Expected imm=64, got {imm}. "
            "_enc_s bit-overlap regression: imm[11:5] must be at <<25, "
            "not <<20."
        )
        assert rs1 == 1, f"rs1 should be x1, got {rs1}"
        assert rs2 == 2, f"rs2 should be x2, got {rs2}"

    def test_sw_round_trip_nonzero_imm(self):
        """Store to offset 32 and load back — verifies encoding is correct."""
        asm = (
            "addi x1, x0, 0\n"    # base = 0
            "addi x2, x0, 123\n"  # value = 123
            "sw x2, 32(x1)\n"     # mem[32] = 123
            "lw x3, 32(x1)\n"     # x3 = mem[32]
            "ecall"
        )
        words = _parse_assembly(asm)
        emu = RiscvEmulator(memory_size=256)
        emu.load_program(words)
        emu.run()
        assert emu.registers[3] == 123, (
            f"Expected x3=123 after sw/lw round-trip, got {emu.registers[3]}. "
            "_enc_s bit-overlap corrupts store address for non-zero imm."
        )


# ---------------------------------------------------------------------------
# Pre-existing emulator decoder bug regressions
# ---------------------------------------------------------------------------

class TestRTypeDecoderRegressions:
    """Pre-existing bug: R-type decoder had a bare `if` at funct3==0x2 (slt)
    that broke the elif chain.  After any ADD/SUB/SLL match (first chain),
    the second chain starting at SLT always evaluated, potentially writing
    a second value into rd.

    Fixed: `if funct3 == 0x2` → `elif funct3 == 0x2`.
    Also: SLT operand comparison corrected to signed (_sign_extend).
    """

    def test_add_does_not_corrupt_rd_via_slt_path(self):
        """add x1, x2, x3 where x2=5, x3=10: result must be 15, not 0."""
        emu = RiscvEmulator()
        words = _parse_assembly("add x1, x2, x3\necall")
        emu.load_program(words)
        emu.registers[2] = 5
        emu.registers[3] = 10
        emu.run()
        assert emu.registers[1] == 15, (
            f"Expected x1=15 from add, got {emu.registers[1]}. "
            "R-type broken elif: slt chain overwrote rd after add matched."
        )

    def test_sub_does_not_corrupt_rd_via_slt_path(self):
        """sub x1, x2, x3 where x2=20, x3=7: result must be 13, not 0."""
        emu = RiscvEmulator()
        words = _parse_assembly("sub x1, x2, x3\necall")
        emu.load_program(words)
        emu.registers[2] = 20
        emu.registers[3] = 7
        emu.run()
        assert emu.registers[1] == 13, (
            f"Expected x1=13 from sub, got {emu.registers[1]}. "
            "R-type broken elif: slt chain overwrote rd after sub matched."
        )

    def test_slt_returns_one_when_rs1_less_than_rs2(self):
        """slt x1, x2, x3: x2 < x3 (signed) → x1 must be 1."""
        emu = RiscvEmulator()
        words = _parse_assembly("slt x1, x2, x3\necall")
        emu.load_program(words)
        emu.registers[2] = 3
        emu.registers[3] = 7
        emu.run()
        assert emu.registers[1] == 1, (
            f"Expected x1=1 from slt (3 < 7), got {emu.registers[1]}."
        )

    def test_slt_returns_zero_when_rs1_not_less_than_rs2(self):
        """slt x1, x2, x3: x2 >= x3 → x1 must be 0."""
        emu = RiscvEmulator()
        words = _parse_assembly("slt x1, x2, x3\necall")
        emu.load_program(words)
        emu.registers[2] = 7
        emu.registers[3] = 3
        emu.run()
        assert emu.registers[1] == 0, (
            f"Expected x1=0 from slt (7 >= 3), got {emu.registers[1]}."
        )

    def test_slt_negative_vs_positive_signed(self):
        """slt x1, x2, x3: x2=-1 (0xFFFFFFFF), x3=1 → x1=1 (signed)."""
        emu = RiscvEmulator()
        words = _parse_assembly("slt x1, x2, x3\necall")
        emu.load_program(words)
        emu.registers[2] = 0xFFFFFFFF  # -1 as signed 32-bit
        emu.registers[3] = 1
        emu.run()
        assert emu.registers[1] == 1, (
            f"Expected slt(-1, 1)=1 (signed), got {emu.registers[1]}. "
            "slt must use signed comparison."
        )


class TestLoadDecoderRegressions:
    """Pre-existing bug: Load decoder had a bare `if` at funct3==0x4 (LBU)
    that broke the elif chain.  After any LB/LH/LW match, the second chain
    (LBU/LHU) always evaluated.  For LW (funct3==0x2), neither 0x4 nor 0x5
    matches so there's no corruption — but LB (0x0) followed by the bare
    if (0x4 check) is always a no-op since 0x0 != 0x4.  The real failure
    mode: LBU (funct3==0x4) now first falls through the top chain as 'no
    match', then the bare `if funct3==0x4` fires — so LBU appears to work
    but only because the two separate chains both miss the top (0x0-0x2) and
    hit the bottom (0x4).  LB (0x0) and LBU (0x4) are now in a single
    unified elif chain so the correct branch fires and only once.

    Fixed: `if funct3 == 0x4` → `elif funct3 == 0x4`.
    """

    def test_lbu_loads_unsigned_byte(self):
        """LBU must zero-extend a byte with high bit set."""
        emu = RiscvEmulator(memory_size=256)
        words = _parse_assembly("lbu x1, 64(x0)\necall")
        emu.load_program(words)
        emu.memory[64] = 0xFF  # write AFTER load_program to avoid overwrite
        emu.run()
        assert emu.registers[1] == 0xFF, (
            f"Expected x1=0xFF (255) from lbu, got {emu.registers[1]}."
        )

    def test_lb_sign_extends_negative_byte(self):
        """LB must sign-extend: byte 0xFF → -1 (Python signed int)."""
        emu = RiscvEmulator(memory_size=256)
        words = _parse_assembly("lb x1, 64(x0)\necall")
        emu.load_program(words)
        emu.memory[64] = 0xFF  # write AFTER load_program
        emu.run()
        assert emu.registers[1] == -1, (
            f"Expected x1=-1 from lb 0xFF (sign-extended), "
            f"got {emu.registers[1]}."
        )

    def test_lbu_and_lb_differ_for_high_bit_byte(self):
        """LBU and LB must produce different results for byte >= 0x80."""
        emu_lb = RiscvEmulator(memory_size=256)
        words_lb = _parse_assembly("lb x1, 64(x0)\necall")
        emu_lb.load_program(words_lb)
        emu_lb.memory[64] = 0x80  # write AFTER load_program
        emu_lb.run()

        emu_lbu = RiscvEmulator(memory_size=256)
        words_lbu = _parse_assembly("lbu x1, 64(x0)\necall")
        emu_lbu.load_program(words_lbu)
        emu_lbu.memory[64] = 0x80  # write AFTER load_program
        emu_lbu.run()

        assert emu_lb.registers[1] != emu_lbu.registers[1], (
            "LB and LBU returned the same value for 0x80 — "
            "broken elif made LBU overwrite LB's sign-extended result."
        )
        assert emu_lbu.registers[1] == 0x80   # unsigned: 128
        assert emu_lb.registers[1] == -0x80   # signed: -128


class TestMemoryBoundsRegressions:
    """Pre-existing bug: load/store with addresses >= memory_size crashed
    with IndexError because the 32-bit address mask (& 0xFFFFFFFF) produced
    values far larger than the bytearray."""

    def test_lw_out_of_bounds_halts(self):
        """lw at address beyond memory should halt gracefully, not crash."""
        emu = RiscvEmulator(memory_size=64)
        # x1=0, imm=64 -> addr=64 which is exactly at memory_size boundary
        words = _parse_assembly("lw x2, 64(x1)\necall")
        emu.load_program(words)
        emu.run()
        # Emulator halted on bounds fault before ecall
        assert emu.instruction_count == 1, (
            "Expected halt on OOB lw, but emulator continued"
        )

    def test_sw_out_of_bounds_halts(self):
        """sw at address beyond memory should halt gracefully."""
        emu = RiscvEmulator(memory_size=64)
        words = _parse_assembly("sw x2, 64(x1)\necall")
        emu.load_program(words)
        emu.run()
        assert emu.instruction_count == 1, (
            "Expected halt on OOB sw, but emulator continued"
        )

    def test_lh_partial_out_of_bounds_halts(self):
        """lh at memory_size-1 should fault (needs 2 bytes)."""
        emu = RiscvEmulator(memory_size=8)
        # The assembler encodes loads with rs1=x0 regardless of the
        # register written in parentheses (pre-existing quirk).
        # imm=7 -> addr=7; LH needs bytes 7 and 8, but 8 is OOB.
        words = _parse_assembly("lh x2, 7(x0)\necall")
        emu.load_program(words)
        emu.run()
        assert emu.instruction_count == 1, (
            f"Expected 1 instruction (lh fault), "
            f"got {emu.instruction_count}"
        )

    def test_in_bounds_access_still_works(self):
        """Valid addresses must still work after bounds check addition."""
        emu = RiscvEmulator(memory_size=256)
        # Use x0 as base because the assembler encodes lw with rs1=x0
        # regardless of the register in parentheses (pre-existing quirk).
        # Place data at addr 16 so the store does not overwrite the lw
        # instruction itself (the program is 3 instructions = 12 bytes).
        words = _parse_assembly(
            "sw x2, 16(x0)\n"     # mem[16] = x2
            "lw x3, 16(x0)\n"     # x3 = mem[16]
            "ecall"
        )
        emu.load_program(words)
        emu.registers[2] = 0xDEADBEEF
        emu.run()
        assert emu.registers[3] == 0xDEADBEEF, (
            f"Expected 0xDEADBEEF, got {emu.registers[3]:#x}. "
            "Bounds check broke valid in-bounds access"
        )
