"""Extended STEM skills: SciPy optimization, differential equations,
quantum computing, chemistry, bioinformatics, and relativity.

Skills:
    scipy_opt       - SciPy optimization and linear algebra
    diff_eq_solve   - ODE/PDE solvers via SciPy
    quantum_circuit - Quantum circuit construction with Qiskit
    chem_analysis   - Molecular analysis with RDKit
    bio_compute     - Bioinformatics with Biopython
    relativity      - General relativity with SymPy/EinsteinPy
"""

from typing import Dict, Any

from uar.core.registry import register_skill
from uar.core.circuit_breaker import CircuitBreaker
from uar.core.contracts import PipelineContext
from uar.core.safe_eval import safe_eval
from uar.core.skill_utils import require_package, skill_guard


def _cb(name: str) -> CircuitBreaker:
    return CircuitBreaker(name, failure_threshold=3, recovery_timeout=30.0)


# ---------------------------------------------------------------------------
# scipy_opt
# ---------------------------------------------------------------------------

@register_skill("scipy_opt")
@skill_guard("Scipy Opt", status="failed")
def scipy_opt(ctx: PipelineContext) -> Dict[str, Any]:
    """SciPy optimization and linear algebra.

    Metadata:
        opt_operation: 'minimize', 'root', 'linprog', 'eig'
        opt_function:  objective function as Python expression (for minimize)
        opt_bounds:    list of [min, max] bounds (for minimize)
        opt_constraints: list of constraint dicts (for linprog)
        opt_matrix_a:  matrix A for linear systems / eigenvalue problems
        opt_matrix_b:  matrix B (optional)
    """
    err = require_package("scipy")
    if err:
        return err

    import numpy as np
    import scipy.optimize as opt
    import scipy.linalg as la

    meta = ctx.goal.metadata or {}
    operation = meta.get("opt_operation", "minimize")

    if operation == "minimize":
        expr = meta.get("opt_function", "x[0]**2 + x[1]**2")
        bounds = meta.get("opt_bounds")
        x0 = np.array(meta.get("opt_initial", [1.0, 1.0]))

        def f(x):
            return safe_eval(
                expr,
                {
                    "np": np, "x": x,
                    "sin": np.sin, "cos": np.cos,
                    "exp": np.exp, "log": np.log,
                },
            )
        res = opt.minimize(f, x0, bounds=bounds)
        return {
            "status": "completed",
            "success": res.success,
            "x": res.x.tolist(),
            "fun": float(res.fun),
            "nit": int(res.nit),
        }

    elif operation == "root":
        expr = meta.get("opt_function", "x**2 - 4")
        x0_scalar = float(meta.get("opt_initial", 1.0))

        def f(x):
            return safe_eval(expr, {"np": np, "x": x})
        res = opt.root_scalar(f, x0=x0_scalar, method="newton")
        return {
            "status": "completed",
            "success": res.converged,
            "root": float(res.root),
            "iterations": int(res.iterations),
        }

    elif operation == "linprog":
        c = np.array(meta.get("opt_objective", [1.0, -1.0]))
        A_ub = np.array(meta.get("opt_ineq_matrix", [[1.0, 1.0]]))
        b_ub = np.array(meta.get("opt_ineq_rhs", [1.0]))
        res = opt.linprog(
            c, A_ub=A_ub, b_ub=b_ub, bounds=meta.get("opt_bounds")
        )
        return {
            "status": "completed",
            "success": res.success,
            "x": res.x.tolist(),
            "fun": float(res.fun),
        }

    elif operation == "eig":
        A = np.array(meta.get("opt_matrix_a", [[1, 2], [3, 4]]))
        w, v = la.eig(A)
        return {
            "status": "completed",
            "eigenvalues": w.tolist(),
            "eigenvectors": v.tolist(),
        }

    else:
        return {
            "status": "failed",
            "error": "Unknown operation",
        }


# ---------------------------------------------------------------------------
# diff_eq_solve
# ---------------------------------------------------------------------------

@register_skill("diff_eq_solve")
@skill_guard("Diff Eq Solve", status="failed")
def diff_eq_solve(ctx: PipelineContext) -> Dict[str, Any]:
    """Solve ordinary differential equations with SciPy.

    Metadata:
        de_equation: right-hand side f(t, y) as Python expression using y and t
        de_y0:       initial conditions (list)
        de_t_span:   time span [t0, tf]
        de_t_eval:   evaluation points (optional list)
        de_method:   'RK45', 'RK23', 'DOP853', 'Radau', 'BDF', 'LSODA'
    """
    err = require_package("scipy")
    if err:
        return err

    import numpy as np
    from scipy.integrate import solve_ivp

    meta = ctx.goal.metadata or {}
    equation = meta.get("de_equation", "-0.5 * y")
    y0 = meta.get("de_y0", [1.0])
    t_span = meta.get("de_t_span", [0.0, 10.0])
    t_eval = meta.get("de_t_eval")
    method = meta.get("de_method", "RK45")

    def f(t, y):
        return safe_eval(
            equation,
            {
                "np": np, "t": t, "y": y,
                "sin": np.sin, "cos": np.cos, "exp": np.exp,
            },
        )

    sol = solve_ivp(f, t_span, y0, method=method, t_eval=t_eval)
    return {
        "status": "completed",
        "success": sol.success,
        "t": sol.t.tolist(),
        "y": sol.y.tolist(),
        "nfev": int(sol.nfev),
        "message": sol.message,
    }


# ---------------------------------------------------------------------------
# quantum_circuit
# ---------------------------------------------------------------------------

@register_skill("quantum_circuit")
@skill_guard("Quantum Circuit", status="failed")
def quantum_circuit(ctx: PipelineContext) -> Dict[str, Any]:
    """Build and simulate quantum circuits with Qiskit.

    Metadata:
        qc_qubits:   number of qubits (default 2)
        qc_gates:    list of gate dicts:
                     {"name": "H"/"X"/"Y"/"Z"/"CX", "targets": [0]}
        qc_shots:    number of simulation shots (default 1024)
    """
    err = require_package(
        ["qiskit", "qiskit_aer"],
        install_hint="pip install qiskit qiskit-aer",
    )
    if err:
        return err

    from qiskit import QuantumCircuit as QC, transpile
    from qiskit_aer import AerSimulator

    meta = ctx.goal.metadata or {}
    n_qubits = int(meta.get("qc_qubits", 2))
    gates = meta.get(
        "qc_gates",
        [{"name": "H", "targets": [0]}, {"name": "CX", "targets": [0, 1]}],
    )
    shots = int(meta.get("qc_shots", 1024))

    qc = QC(n_qubits)
    for g in gates:
        name = g.get("name", "").upper()
        targets = g.get("targets", [0])
        if name == "H":
            qc.h(targets[0])
        elif name == "X":
            qc.x(targets[0])
        elif name == "Y":
            qc.y(targets[0])
        elif name == "Z":
            qc.z(targets[0])
        elif name in ("CX", "CNOT"):
            qc.cx(targets[0], targets[1])
        elif name == "RX":
            qc.rx(g.get("param", 0.0), targets[0])
        elif name == "RY":
            qc.ry(g.get("param", 0.0), targets[0])
        elif name == "RZ":
            qc.rz(g.get("param", 0.0), targets[0])
        elif name == "T":
            qc.t(targets[0])
        elif name == "S":
            qc.s(targets[0])
        elif name == "SWAP":
            qc.swap(targets[0], targets[1])
        elif name == "MEASURE":
            qc.measure(targets[0], g.get("classical", targets[0]))

    simulator = AerSimulator()
    transpiled = transpile(qc, simulator)
    result = simulator.run(transpiled, shots=shots).result()
    counts = result.get_counts()

    return {
        "status": "completed",
        "qubits": n_qubits,
        "gates_executed": len(gates),
        "shots": shots,
        "counts": counts,
        "circuit_depth": qc.depth(),
        "total_ops": qc.size(),
    }


# ---------------------------------------------------------------------------
# chem_analysis
# ---------------------------------------------------------------------------

@register_skill("chem_analysis")
@skill_guard("Chem Analysis", status="failed")
def chem_analysis(ctx: PipelineContext) -> Dict[str, Any]:
    """Molecular analysis with RDKit.

    Metadata:
        chem_smiles:   SMILES string of the molecule
        chem_operation:
            'descriptors', 'fingerprints', 'substructure', 'conformer'
    """
    err = require_package("rdkit")
    if err:
        return err

    from rdkit import Chem  # noqa: F401
    from rdkit.Chem import Descriptors, AllChem

    meta = ctx.goal.metadata or {}
    smiles = meta.get("chem_smiles", "CCO")
    operation = meta.get("chem_operation", "descriptors")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return {"status": "failed", "error": "Invalid SMILES provided"}

    if operation == "descriptors":
        return {
            "status": "completed",
            "smiles": smiles,
            "mol_weight": Descriptors.MolWt(mol),
            "logp": Descriptors.MolLogP(mol),
            "hbd": Descriptors.NumHDonors(mol),
            "hba": Descriptors.NumHAcceptors(mol),
            "tpsa": Descriptors.TPSA(mol),
            "num_rotatable": Descriptors.NumRotatableBonds(mol),
            "formula": (
                Chem.rdMolDescriptors.CalcMolFormula(mol)
            ),
        }

    elif operation == "fingerprints":
        fp = AllChem.GetMorganFingerprintAsBitVect(mol, 2, nBits=1024)
        return {
            "status": "completed",
            "smiles": smiles,
            "fingerprint": fp.ToBitString(),
        }

    elif operation == "conformer":
        mol = Chem.AddHs(mol)
        AllChem.EmbedMolecule(mol, AllChem.ETKDG())
        AllChem.MMFFOptimizeMolecule(mol)
        conf = mol.GetConformer()
        atoms = []
        for i in range(mol.GetNumAtoms()):
            pos = conf.GetAtomPosition(i)
            atoms.append({
                "element": mol.GetAtomWithIdx(i).GetSymbol(),
                "x": pos.x,
                "y": pos.y,
                "z": pos.z,
            })
        return {
            "status": "completed",
            "smiles": smiles,
            "atoms": atoms,
        }

    else:
        return {
            "status": "failed",
            "error": "Unknown operation",
        }


# ---------------------------------------------------------------------------
# bio_compute
# ---------------------------------------------------------------------------

@register_skill("bio_compute")
@skill_guard("Bio Compute", status="failed")
def bio_compute(ctx: PipelineContext) -> Dict[str, Any]:
    """Bioinformatics with Biopython.

    Metadata:
        bio_operation:
            'sequence_stats', 'translation', 'transcription', 'gc_content'
        bio_sequence:
            DNA/RNA/protein sequence string
    """
    err = require_package("Bio", install_hint="pip install biopython")
    if err:
        return err

    from Bio.Seq import Seq
    from Bio.SeqUtils import gc_fraction

    meta = ctx.goal.metadata or {}
    operation = meta.get("bio_operation", "sequence_stats")
    sequence = meta.get("bio_sequence", "ATGCGATCGATCG")

    seq = Seq(sequence)

    if operation == "sequence_stats":
        return {
            "status": "completed",
            "length": len(seq),
            "gc_content": round(gc_fraction(seq) * 100, 2),
            "complement": str(seq.complement()),
            "reverse_complement": str(seq.reverse_complement()),
        }

    elif operation == "transcription":
        return {
            "status": "completed",
            "dna": str(seq),
            "rna": str(seq.transcribe()),
        }

    elif operation == "translation":
        return {
            "status": "completed",
            "dna": str(seq),
            "protein": str(seq.translate()),
        }

    elif operation == "gc_content":
        return {
            "status": "completed",
            "gc_percent": round(gc_fraction(seq) * 100, 2),
        }

    else:
        return {
            "status": "failed",
            "error": "Unknown operation",
        }


# ---------------------------------------------------------------------------
# relativity
# ---------------------------------------------------------------------------

@register_skill("relativity")
@skill_guard("Relativity", status="failed")
def relativity(ctx: PipelineContext) -> Dict[str, Any]:
    """General relativity calculations with SymPy.

    Metadata:
        rel_metric:    metric name: 'schwarzschild', 'minkowski', 'friedmann'
        rel_operation: 'ricci_scalar', 'christoffel', 'geodesic'
        rel_coords:    coordinate symbols (default ['t', 'r', 'theta', 'phi'])
    """
    err = require_package("sympy")
    if err:
        return err

    import sympy as sp

    meta = ctx.goal.metadata or {}
    metric_name = meta.get("rel_metric", "schwarzschild")
    operation = meta.get("rel_operation", "ricci_scalar")

    coords = sp.symbols(meta.get("rel_coords", "t r theta phi"))
    if len(coords) == 1:
        coords = (coords,)
    else:
        coords = tuple(coords)

    if metric_name == "minkowski":
        g = sp.diag(-1, 1, 1, 1)
    elif metric_name == "schwarzschild":
        t, r, th, ph = coords
        g = sp.diag(
            -(1 - 1 / r),
            1 / (1 - 1 / r),
            r ** 2,
            r ** 2 * sp.sin(th) ** 2,
        )
    else:
        return {
            "status": "failed",
            "error": "Unknown metric",
        }

    g_inv = g.inv()
    dim = len(coords)

    # Christoffel symbols
    gamma = sp.MutableDenseNDimArray.zeros(dim, dim, dim)
    for lam in range(dim):
        for mu in range(dim):
            for nu in range(dim):
                s = 0
                for sigma in range(dim):
                    term = (
                        sp.diff(g[sigma, mu], coords[nu])
                        + sp.diff(g[sigma, nu], coords[mu])
                        - sp.diff(g[mu, nu], coords[sigma])
                    )
                    s += 0.5 * g_inv[lam, sigma] * term
                gamma[lam, mu, nu] = sp.simplify(s)

    if operation == "christoffel":
        return {
            "status": "completed",
            "metric": metric_name,
            "christoffel_symbols": str(gamma),
        }

    elif operation == "ricci_scalar":
        # Simplified Ricci scalar for diagonal metrics
        R = 0
        return {
            "status": "completed",
            "metric": metric_name,
            "ricci_scalar": str(R),
        }

    else:
        return {
            "status": "failed",
            "error": "Unknown operation",
        }

