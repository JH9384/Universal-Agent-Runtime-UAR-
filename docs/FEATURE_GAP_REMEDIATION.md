# UAR Feature Gap Remediation Plan

This document maps each identified gap to a specific GitHub repository that can remediate it. The goal is to make every README claim fully real.

## Gap 1: Molecular Visualization (Hardcoded Coordinates)

**Current:** `molecular_visualization.py` uses hardcoded simplified coordinates for water, methane, benzene, caffeine.

**What it should do:** Generate accurate 3D geometries from SMILES strings using force-field optimization.

**GitHub Repository:** [rdkit/rdkit](https://github.com/rdkit/rdkit)
- RDKit is the industry-standard open-source cheminformatics toolkit
- Can parse SMILES → generate 2D/3D coordinates → optimize with force fields (MMFF, UFF)
- Has Python bindings and is BSD-licensed

**Implementation:**
```python
from rdkit import Chem
from rdkit.Chem import AllChem

mol = Chem.MolFromSmiles("CN1C=NC2=C1C(=O)N(C(=O)N2C)C")  # caffeine
mol = Chem.AddHs(mol)
AllChem.EmbedMolecule(mol, AllChem.ETKDG())
AllChem.MMFFOptimizeMolecule(mol)
conformer = mol.GetConformer()
# Extract 3D coordinates from conformer
```

**Alternative:** [ase/ase](https://github.com/ase/ase) (Atomic Simulation Environment) for quantum-mechanical geometry optimization.

---

## Gap 2: RISC-V Emulator (Instruction-Level, Not Cycle-Accurate)

**Current:** `riscv_sim.py` is an instruction-level interpreter. `riscv_cycle.py` simulates a pipeline but not a real 5-stage microarchitecture.

**What it should do:** Provide cycle-accurate RV32I emulation with pipeline hazards, forwarding, and branch prediction.

**GitHub Repository:** [riscv-software-src/riscv-isa-sim](https://github.com/riscv-software-src/riscv-isa-sim) (Spike)
- The official RISC-V ISA simulator from UC Berkeley
- Cycle-accurate, supports RV32I/RV64I, privilege modes, memory models
- Can be wrapped as a Python subprocess or compiled as a shared library

**Alternative:** [ucb-bar/chipyard](https://github.com/ucb-bar/chipyard) for full SoC simulation with Chisel-generated cores.

**Implementation:** Wrap Spike as a subprocess skill:
```python
subprocess.run([
    "spike", "--isa=RV32I",
    "pk", "program.elf"
], capture_output=True)
```

---

## Gap 3: Quantum Circuit (No Hardware Execution)

**Current:** `quantum_circuit_visualization.py` generates 3D layout data but doesn't execute on quantum hardware.

**What it should do:** Compile circuits to Qiskit and run on IBM Quantum simulators or real hardware.

**GitHub Repository:** [Qiskit/qiskit](https://github.com/Qiskit/qiskit)
- IBM's open-source quantum computing SDK
- Can run on `AerSimulator` (local) or IBM Quantum hardware (cloud)
- Generates actual measurement results, not just geometry

**Implementation:**
```python
from qiskit import QuantumCircuit
from qiskit_aer import AerSimulator

qc = QuantumCircuit(2)
qc.h(0)
qc.cx(0, 1)
qc.measure_all()

sim = AerSimulator()
result = sim.run(qc).result()
counts = result.get_counts()
```

**Alternative:** [quantumlib/Cirq](https://github.com/quantumlib/Cirq) for Google's quantum framework.

---

## Gap 4: Browser-Accessible Scientific Computing Sandbox

**Current:** Web UI is a React control surface. No interactive Python execution in browser.

**What it should do:** Users can write and run Python code in the browser without a backend.

**GitHub Repository:** [pyodide/pyodide](https://github.com/pyodide/pyodide)
- Python distribution compiled to WebAssembly that runs entirely in the browser
- Includes NumPy, SciPy, Matplotlib, Pandas, scikit-learn
- Can install pure-Python wheels from PyPI

**Alternative:** [jupyterlite/jupyterlite](https://github.com/jupyterlite/jupyterlite) for full Jupyter notebooks in browser.

**Implementation:** Embed Pyodide in the operator dashboard:
```html
<script src="https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js"></script>
<script>
async function main() {
  let pyodide = await loadPyodide();
  await pyodide.loadPackage("numpy");
  console.log(pyodide.runPython("import numpy; numpy.array([1,2,3])"));
}
</script>
```

---

## Gap 5: Production Security Hardening

**Current:** Has rate limiting, CORS, auth, SSRF. Missing: TrustedHostMiddleware, HSTS, CSP, security headers.

**What it should do:** Pass OWASP API Security Top 10 checks out of the box.

**GitHub Repository:** [rennf93/fastapi-guard](https://github.com/rennf93/fastapi-guard)
- Security middleware for FastAPI: IP control, logging, penetration detection
- Drop-in integration with existing FastAPI apps

**Additional Resources:**
- [VolkanSah/Securing-FastAPI-Applications](https://github.com/VolkanSah/Securing-FastAPI-Applications) — comprehensive guide
- [zhanymkanov/fastapi-best-practices](https://github.com/zhanymkanov/fastapi-best-practices) — production patterns

**Implementation:** Add TrustedHostMiddleware, HSTS, and CSP headers to `uar/api/server.py`.

---

## Gap 6: Schemathesis Fuzz Test Failures

**Current:** 2 failures in `tests/api/test_schemathesis_fuzz.py` for `POST /agents/workflow/run` and `POST /workflows/run`.

**What it should do:** All API endpoints pass property-based fuzz testing.

**GitHub Repository:** [schemathesis/schemathesis](https://github.com/schemathesis/schemathesis)
- The fuzz testing framework itself
- Can generate targeted test cases and shrink failing inputs

**Remediation:** Run schemathesis locally to capture the actual failing payloads:
```bash
st run http://127.0.0.1:8000/openapi.json --hypothesis-seed=12345
```

---

## Summary Table

| Gap | Repository | License | Effort |
|-----|-----------|---------|--------|
| Molecular geometry | rdkit/rdkit | BSD | Medium |
| RISC-V cycle accuracy | riscv-software-src/riscv-isa-sim | BSD | High |
| Quantum execution | Qiskit/qiskit | Apache 2.0 | Low |
| Browser sandbox | pyodide/pyodide | MPL-2.0 | Medium |
| Security hardening | rennf93/fastapi-guard | MIT | Low |
| Fuzz failures | schemathesis/schemathesis | MIT | Low |

---

## Priority Order (Recommended)

1. **Quantum execution** (Qiskit) — easiest win, high impact
2. **Security hardening** (fastapi-guard) — low effort, high safety
3. **Browser sandbox** (Pyodide) — medium effort, huge UX win
4. **Molecular geometry** (RDKit) — medium effort, scientific credibility
5. **RISC-V cycle accuracy** (Spike) — high effort, niche but impressive
6. **Fix fuzz failures** — blockers for claiming "production-ready"
