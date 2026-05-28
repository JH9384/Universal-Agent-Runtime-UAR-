"""Tests for stem_extended with mocked heavy dependencies.

Covers scipy_opt, diff_eq_solve, quantum_circuit, chem_analysis,
bio_compute, and relativity when deps are mocked as available.
"""

from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.stem_extended import (
    scipy_opt,
    diff_eq_solve,
    quantum_circuit,
    chem_analysis,
    bio_compute,
    relativity,
)


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(id="t", user_intent="t", objective="t", metadata=meta)
    )


class TestScipyOptMocked:
    """scipy_opt with mocked scipy and numpy."""

    def _mock_modules(self):
        np = MagicMock()
        np.sin = MagicMock(return_value=0.5)
        np.cos = MagicMock(return_value=0.5)
        np.exp = MagicMock(return_value=1.0)
        np.log = MagicMock(return_value=0.0)
        np.array.return_value = [1.0, 1.0]

        mock_res = MagicMock()
        mock_res.success = True
        mock_res.x = MagicMock()
        mock_res.x.tolist.return_value = [0.5, 0.5]
        mock_res.fun = 0.25
        mock_res.nit = 5
        mock_res.converged = True
        mock_res.root = 2.0
        mock_res.iterations = 4

        opt = MagicMock()
        opt.minimize.return_value = mock_res
        opt.root_scalar.return_value = mock_res
        opt.linprog.return_value = mock_res

        la = MagicMock()
        w = MagicMock()
        w.tolist.return_value = [1.0, 2.0]
        v = MagicMock()
        v.tolist.return_value = [[1, 0], [0, 1]]
        la.eig.return_value = (w, v)

        return np, opt, la

    def _setup_scipy(self, np, opt, la):
        mock_scipy = MagicMock()
        mock_scipy.optimize = opt
        mock_scipy.linalg = la
        return {
            "numpy": np,
            "scipy": mock_scipy,
            "scipy.optimize": opt,
            "scipy.linalg": la,
        }

    def test_minimize(self):
        np, opt, la = self._mock_modules()
        with patch.dict("sys.modules", self._setup_scipy(np, opt, la)):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = scipy_opt(
                    _ctx({"opt_operation": "minimize"})
                )
        assert result["status"] == "completed"
        assert result["success"] is True

    def test_root(self):
        np, opt, la = self._mock_modules()
        with patch.dict("sys.modules", self._setup_scipy(np, opt, la)):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = scipy_opt(
                    _ctx({"opt_operation": "root"})
                )
        assert result["status"] == "completed"

    def test_linprog(self):
        np, opt, la = self._mock_modules()
        with patch.dict("sys.modules", self._setup_scipy(np, opt, la)):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = scipy_opt(
                    _ctx({"opt_operation": "linprog"})
                )
        assert result["status"] == "completed"

    def test_eig(self):
        np, opt, la = self._mock_modules()
        with patch.dict("sys.modules", self._setup_scipy(np, opt, la)):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = scipy_opt(
                    _ctx({"opt_operation": "eig"})
                )
        assert result["status"] == "completed"
        assert "eigenvalues" in result

    def test_unknown_operation(self):
        np, opt, la = self._mock_modules()
        with patch.dict("sys.modules", self._setup_scipy(np, opt, la)):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = scipy_opt(
                    _ctx({"opt_operation": "unknown"})
                )
        assert result["status"] == "failed"


class TestDiffEqSolveMocked:
    """diff_eq_solve with mocked scipy."""

    def test_basic(self):
        np = MagicMock()
        sol = MagicMock()
        sol.success = True
        sol.t = MagicMock()
        sol.t.tolist.return_value = [0, 1, 2]
        sol.y = MagicMock()
        sol.y.tolist.return_value = [[1, 0.5, 0.25]]
        sol.nfev = 10
        sol.message = "ok"
        solve_ivp = MagicMock(return_value=sol)
        with patch.dict("sys.modules", {
            "numpy": np,
            "scipy.integrate": MagicMock(solve_ivp=solve_ivp),
        }):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = diff_eq_solve(
                    _ctx({
                        "de_equation": "-0.5 * y",
                        "de_y0": [1.0],
                        "de_t_span": [0.0, 10.0],
                    })
                )
        assert result["status"] == "completed"
        assert result["success"] is True


class TestQuantumCircuitMocked:
    """quantum_circuit with mocked qiskit."""

    def test_basic(self):
        qc = MagicMock()
        qc.depth.return_value = 5
        qc.size.return_value = 10
        QC = MagicMock(return_value=qc)

        simulator = MagicMock()
        result = MagicMock()
        result.get_counts.return_value = {"00": 512, "11": 512}
        simulator.run.return_value.result.return_value = result

        mock_qiskit = MagicMock()
        mock_qiskit.QuantumCircuit = QC
        mock_qiskit.transpile = MagicMock(return_value=qc)

        mock_aer = MagicMock()
        mock_aer.AerSimulator.return_value = simulator

        with patch.dict("sys.modules", {
            "qiskit": mock_qiskit,
            "qiskit_aer": mock_aer,
        }):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = quantum_circuit(
                    _ctx({
                        "qc_qubits": 2,
                        "qc_gates": [
                            {"name": "H", "targets": [0]},
                            {"name": "CX", "targets": [0, 1]},
                        ],
                        "qc_shots": 1024,
                    })
                )
        assert result["status"] == "completed"
        assert result["qubits"] == 2


class TestChemAnalysisMocked:
    """chem_analysis with mocked RDKit."""

    def _setup_rdkit(
        self, Chem, Descriptors=None, AllChem=None, rdMolDescriptors=None
    ):
        mock_rdkit = MagicMock()
        mock_rdkit.Chem = Chem
        modules = {
            "rdkit": mock_rdkit,
            "rdkit.Chem": Chem,
        }
        if Descriptors:
            modules["rdkit.Chem.Descriptors"] = Descriptors
        if AllChem:
            modules["rdkit.Chem.AllChem"] = AllChem
        if rdMolDescriptors:
            modules["rdkit.Chem.rdMolDescriptors"] = rdMolDescriptors
        return modules

    def test_descriptors(self):
        mol = MagicMock()
        Chem = MagicMock()
        Chem.MolFromSmiles.return_value = mol
        Descriptors = MagicMock()
        Descriptors.MolWt.return_value = 46.07
        Descriptors.MolLogP.return_value = -0.14
        Descriptors.NumHDonors.return_value = 1
        Descriptors.NumHAcceptors.return_value = 1
        Descriptors.TPSA.return_value = 20.23
        Descriptors.NumRotatableBonds.return_value = 0
        rdMolDescriptors = MagicMock()
        rdMolDescriptors.CalcMolFormula = lambda m: "C2H6O"

        with patch.dict("sys.modules", self._setup_rdkit(
            Chem, Descriptors, MagicMock(), rdMolDescriptors
        )):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = chem_analysis(
                    _ctx({
                        "chem_smiles": "CCO",
                        "chem_operation": "descriptors",
                    })
                )
        assert result["status"] == "completed"
        assert result["smiles"] == "CCO"

    def test_invalid_smiles(self):
        Chem = MagicMock()
        Chem.MolFromSmiles.return_value = None
        with patch.dict("sys.modules", self._setup_rdkit(
            Chem, MagicMock(), MagicMock()
        )):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = chem_analysis(
                    _ctx({
                        "chem_smiles": "INVALID",
                        "chem_operation": "descriptors",
                    })
                )
        assert result["status"] == "failed"


class TestBioComputeMocked:
    """bio_compute with mocked Biopython."""

    def _mock_bio(self):
        seq = MagicMock()
        seq.__len__ = MagicMock(return_value=13)
        seq.__str__ = MagicMock(return_value="ATGCGATCGATCG")
        seq.complement.return_value = "TACGCTAGCTAGC"
        seq.reverse_complement.return_value = "CGATCGATCGCAT"
        seq.transcribe.return_value = "AUGCGAUCGAUCG"
        seq.translate.return_value = "MRID"

        Seq = MagicMock(return_value=seq)
        gc_fraction = MagicMock(return_value=0.46)
        return Seq, gc_fraction

    def test_sequence_stats(self):
        Seq, gc_fraction = self._mock_bio()
        with patch.dict("sys.modules", {
            "Bio": MagicMock(),
            "Bio.Seq": MagicMock(Seq=Seq),
            "Bio.SeqUtils": MagicMock(gc_fraction=gc_fraction),
        }):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = bio_compute(
                    _ctx({"bio_operation": "sequence_stats"})
                )
        assert result["status"] == "completed"

    def test_transcription(self):
        Seq, gc_fraction = self._mock_bio()
        with patch.dict("sys.modules", {
            "Bio": MagicMock(),
            "Bio.Seq": MagicMock(Seq=Seq),
            "Bio.SeqUtils": MagicMock(gc_fraction=gc_fraction),
        }):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = bio_compute(
                    _ctx({"bio_operation": "transcription"})
                )
        assert result["status"] == "completed"
        assert "rna" in result

    def test_translation(self):
        Seq, gc_fraction = self._mock_bio()
        with patch.dict("sys.modules", {
            "Bio": MagicMock(),
            "Bio.Seq": MagicMock(Seq=Seq),
            "Bio.SeqUtils": MagicMock(gc_fraction=gc_fraction),
        }):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = bio_compute(
                    _ctx({"bio_operation": "translation"})
                )
        assert result["status"] == "completed"
        assert "protein" in result

    def test_gc_content(self):
        Seq, gc_fraction = self._mock_bio()
        with patch.dict("sys.modules", {
            "Bio": MagicMock(),
            "Bio.Seq": MagicMock(Seq=Seq),
            "Bio.SeqUtils": MagicMock(gc_fraction=gc_fraction),
        }):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = bio_compute(
                    _ctx({"bio_operation": "gc_content"})
                )
        assert result["status"] == "completed"

    def test_unknown_operation(self):
        Seq, gc_fraction = self._mock_bio()
        with patch.dict("sys.modules", {
            "Bio": MagicMock(),
            "Bio.Seq": MagicMock(Seq=Seq),
            "Bio.SeqUtils": MagicMock(gc_fraction=gc_fraction),
        }):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = bio_compute(
                    _ctx({"bio_operation": "unknown"})
                )
        assert result["status"] == "failed"


class TestRelativityMocked:
    """relativity with mocked sympy."""

    def test_minkowski_christoffel(self):
        sp = MagicMock()
        t, r, th, ph = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        sp.symbols.return_value = (t, r, th, ph)
        diag = MagicMock()
        diag.inv.return_value = MagicMock()
        sp.diag.return_value = diag
        sp.diff = MagicMock(return_value=0)
        sp.MutableDenseNDimArray.zeros.return_value = MagicMock()
        sp.simplify = MagicMock(return_value=0)

        with patch.dict("sys.modules", {"sympy": sp}):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = relativity(
                    _ctx({
                        "rel_metric": "minkowski",
                        "rel_operation": "christoffel",
                    })
                )
        assert result["status"] == "completed"
        assert result["metric"] == "minkowski"

    def test_schwarzschild_ricci(self):
        sp = MagicMock()
        t, r, th, ph = MagicMock(), MagicMock(), MagicMock(), MagicMock()
        sp.symbols.return_value = (t, r, th, ph)
        diag = MagicMock()
        diag.inv.return_value = MagicMock()
        sp.diag.return_value = diag
        sp.diff = MagicMock(return_value=0)
        sp.MutableDenseNDimArray.zeros.return_value = MagicMock()
        sp.simplify = MagicMock(return_value=0)

        with patch.dict("sys.modules", {"sympy": sp}):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = relativity(
                    _ctx({
                        "rel_metric": "schwarzschild",
                        "rel_operation": "ricci_scalar",
                    })
                )
        assert result["status"] == "completed"

    def test_unknown_metric(self):
        sp = MagicMock()
        sp.symbols.return_value = (MagicMock(),) * 4
        with patch.dict("sys.modules", {"sympy": sp}):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = relativity(
                    _ctx({
                        "rel_metric": "unknown",
                        "rel_operation": "christoffel",
                    })
                )
        assert result["status"] == "failed"

    def test_unknown_operation(self):
        sp = MagicMock()
        sp.symbols.return_value = (MagicMock(),) * 4
        diag = MagicMock()
        diag.inv.return_value = MagicMock()
        sp.diag.return_value = diag
        sp.diff = MagicMock(return_value=0)
        sp.MutableDenseNDimArray.zeros.return_value = MagicMock()
        sp.simplify = MagicMock(return_value=0)

        with patch.dict("sys.modules", {"sympy": sp}):
            with patch(
                "uar.skills.stem_extended.require_package",
                return_value=None,
            ):
                result = relativity(
                    _ctx({
                        "rel_metric": "minkowski",
                        "rel_operation": "unknown_op",
                    })
                )
        assert result["status"] == "failed"
