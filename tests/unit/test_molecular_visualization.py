"""Tests for uar.skills.molecular_visualization."""

from unittest.mock import MagicMock, patch

from uar.skills.molecular_visualization import (
    _compute_bonds,
    _generate_protein_backbone,
    _parse_smiles_basic,
    _rdkit_generate,
    molecular_visualization,
)


class TestComputeBonds:
    def test_water(self):
        atoms = [
            {"element": "O", "x": 0.0, "y": 0.0, "z": 0.0},
            {"element": "H", "x": 0.757, "y": 0.586, "z": 0.0},
            {"element": "H", "x": -0.757, "y": 0.586, "z": 0.0},
        ]
        bonds = _compute_bonds(atoms)
        assert len(bonds) == 2

    def test_methane(self):
        atoms = [
            {"element": "C", "x": 0.0, "y": 0.0, "z": 0.0},
            {"element": "H", "x": 0.63, "y": 0.63, "z": 0.63},
            {"element": "H", "x": -0.63, "y": -0.63, "z": 0.63},
            {"element": "H", "x": -0.63, "y": 0.63, "z": -0.63},
            {"element": "H", "x": 0.63, "y": -0.63, "z": -0.63},
        ]
        bonds = _compute_bonds(atoms)
        assert len(bonds) == 4

    def test_unknown_element(self):
        atoms = [
            {"element": "X", "x": 0.0, "y": 0.0, "z": 0.0},
            {"element": "Y", "x": 0.5, "y": 0.0, "z": 0.0},
        ]
        bonds = _compute_bonds(atoms)
        assert len(bonds) == 1

    def test_empty(self):
        assert _compute_bonds([]) == []

    def test_single_atom(self):
        assert _compute_bonds([{"element": "C", "x": 0, "y": 0, "z": 0}]) == []

    def test_no_bonds(self):
        atoms = [
            {"element": "H", "x": 0.0, "y": 0.0, "z": 0.0},
            {"element": "H", "x": 10.0, "y": 0.0, "z": 0.0},
        ]
        assert _compute_bonds(atoms) == []


class TestGenerateProteinBackbone:
    def test_default(self):
        atoms = _generate_protein_backbone()
        assert len(atoms) == 40  # 4 atoms * 10 residues
        assert atoms[0]["element"] == "N"
        assert atoms[1]["element"] == "C"

    def test_custom_residues(self):
        atoms = _generate_protein_backbone(residues=5)
        assert len(atoms) == 20


class TestParseSmilesBasic:
    def test_simple_chain(self):
        atoms = _parse_smiles_basic("CCO")
        assert len(atoms) == 3
        assert atoms[0]["element"] == "C"
        assert atoms[1]["element"] == "C"
        assert atoms[2]["element"] == "O"

    def test_bond_types(self):
        atoms = _parse_smiles_basic("C=C#C")
        assert len(atoms) == 3
        assert atoms[0]["element"] == "C"
        assert atoms[1]["element"] == "C"
        assert atoms[2]["element"] == "C"

    def test_cl(self):
        atoms = _parse_smiles_basic("CCl")
        assert len(atoms) == 2
        assert atoms[1]["element"] == "Cl"

    def test_br(self):
        atoms = _parse_smiles_basic("CBr")
        assert len(atoms) == 2
        assert atoms[1]["element"] == "Br"

    def test_aromatic_c(self):
        atoms = _parse_smiles_basic("c1ccccc1")
        assert len(atoms) == 6
        assert all(a["element"] == "C" for a in atoms)

    def test_aromatic_n(self):
        atoms = _parse_smiles_basic("n1cccc1")
        assert len(atoms) == 5
        assert atoms[0]["element"] == "N"
        assert atoms[1]["element"] == "C"

    def test_aromatic_o(self):
        atoms = _parse_smiles_basic("o1ccc1")
        assert len(atoms) == 4
        assert atoms[0]["element"] == "O"
        assert atoms[1]["element"] == "C"

    def test_aromatic_s(self):
        atoms = _parse_smiles_basic("s1ccc1")
        assert len(atoms) == 4
        assert atoms[0]["element"] == "S"
        assert atoms[1]["element"] == "C"

    def test_parentheses(self):
        atoms = _parse_smiles_basic("C(C)O")
        assert len(atoms) == 3

    def test_brackets(self):
        atoms = _parse_smiles_basic("C[CH]O")
        assert len(atoms) == 4  # C, C, H, O (brackets skipped)

    def test_digits(self):
        atoms = _parse_smiles_basic("C1CC1")
        assert len(atoms) == 3

    def test_unknown_chars(self):
        atoms = _parse_smiles_basic("C@N")
        assert len(atoms) == 2

    def test_empty(self):
        atoms = _parse_smiles_basic("")
        assert atoms == []

    def test_no_atoms(self):
        atoms = _parse_smiles_basic("=-#()[]123")
        assert atoms == []

    def test_elements(self):
        for el in ["N", "O", "S", "P", "F", "I", "H"]:
            atoms = _parse_smiles_basic(el)
            assert len(atoms) == 1
            assert atoms[0]["element"] == el


class TestRdkitGenerate:
    def test_import_error(self):
        with patch.dict("sys.modules", {"rdkit": None}):
            assert _rdkit_generate("CCO") is None

    def test_invalid_smiles(self):
        mock_chem = MagicMock()
        mock_chem.MolFromSmiles.return_value = None
        mock_rdkit = MagicMock()
        mock_rdkit.Chem = mock_chem
        with patch.dict("sys.modules", {
            "rdkit": mock_rdkit,
            "rdkit.Chem": mock_chem,
        }):
            assert _rdkit_generate("bad") is None

    def test_success(self):
        mock_atom = MagicMock()
        mock_atom.GetSymbol.return_value = "C"
        mock_pos = MagicMock()
        mock_pos.x = 1.0
        mock_pos.y = 2.0
        mock_pos.z = 3.0
        mock_conf = MagicMock()
        mock_conf.GetAtomPosition.return_value = mock_pos
        mock_mol = MagicMock()
        mock_mol.GetNumAtoms.return_value = 1
        mock_mol.GetConformer.return_value = mock_conf
        mock_mol.GetAtomWithIdx.return_value = mock_atom
        mock_chem = MagicMock()
        mock_chem.MolFromSmiles.return_value = mock_mol
        mock_chem.AddHs.return_value = mock_mol
        mock_allchem = MagicMock()
        mock_rdkit = MagicMock()
        mock_rdkit.Chem = mock_chem
        with patch.dict("sys.modules", {
            "rdkit": mock_rdkit,
            "rdkit.Chem": mock_chem,
            "rdkit.Chem.AllChem": mock_allchem,
        }):
            result = _rdkit_generate("C")
        assert result is not None
        assert result[0]["element"] == "C"
        assert result[0]["x"] == 1.0


class TestMolecularVisualization:
    def _make_ctx(self, metadata):
        ctx = MagicMock()
        ctx.goal.metadata = metadata
        ctx.goal.user_intent = "viz"
        return ctx

    def test_default_water(self):
        ctx = self._make_ctx({})
        result = molecular_visualization(ctx)
        assert result["status"] == "completed"
        assert result["result"]["molecule"] == "water"
        assert result["result"]["source"] == "hardcoded"
        assert result["result"]["atom_count"] == 3

    def test_methane(self):
        ctx = self._make_ctx({"molecule": "methane"})
        result = molecular_visualization(ctx)
        assert result["result"]["atom_count"] == 5

    def test_benzene(self):
        ctx = self._make_ctx({"molecule": "benzene"})
        result = molecular_visualization(ctx)
        assert result["result"]["atom_count"] == 12

    def test_caffeine(self):
        ctx = self._make_ctx({"molecule": "caffeine"})
        result = molecular_visualization(ctx)
        assert result["result"]["atom_count"] == 10

    def test_unknown_molecule(self):
        ctx = self._make_ctx({"molecule": "xyz"})
        result = molecular_visualization(ctx)
        assert result["result"]["molecule"] == "xyz"
        assert result["result"]["atom_count"] == 3  # falls back to water

    def test_protein(self):
        ctx = self._make_ctx({"molecule": "protein", "residues": 5})
        result = molecular_visualization(ctx)
        assert result["result"]["source"] == "protein_backbone"
        assert result["result"]["atom_count"] == 20

    def test_smiles_fallback(self):
        ctx = self._make_ctx({"smiles": "CCO"})
        with patch(
            "uar.skills.molecular_visualization._rdkit_generate",
            return_value=None,
        ):
            result = molecular_visualization(ctx)
        assert result["result"]["source"] == "smiles"
        assert result["result"]["smiles"] == "CCO"
        assert result["result"]["atom_count"] == 3

    def test_smiles_priority(self):
        """SMILES takes priority over molecule name."""
        ctx = self._make_ctx({"smiles": "C", "molecule": "water"})
        with patch(
            "uar.skills.molecular_visualization._rdkit_generate",
            return_value=None,
        ):
            result = molecular_visualization(ctx)
        assert result["result"]["source"] == "smiles"
        assert result["result"]["molecule"] == "water"

    def test_rdkit_success(self):
        ctx = self._make_ctx({"smiles": "C"})
        mock_atom = MagicMock()
        mock_atom.GetSymbol.return_value = "C"
        mock_pos = MagicMock(x=1.0, y=2.0, z=3.0)
        mock_conf = MagicMock()
        mock_conf.GetAtomPosition.return_value = mock_pos
        mock_mol = MagicMock()
        mock_mol.GetNumAtoms.return_value = 1
        mock_mol.GetConformer.return_value = mock_conf
        mock_mol.GetAtomWithIdx.return_value = mock_atom
        mock_chem = MagicMock()
        mock_chem.MolFromSmiles.return_value = mock_mol
        mock_chem.AddHs.return_value = mock_mol
        mock_rdkit = MagicMock()
        mock_rdkit.Chem = mock_chem
        with patch.dict("sys.modules", {
            "rdkit": mock_rdkit,
            "rdkit.Chem": mock_chem,
            "rdkit.Chem.AllChem": MagicMock(),
        }):
            result = molecular_visualization(ctx)
        assert result["result"]["source"] == "smiles"
        assert result["result"]["atom_count"] == 1

    def test_centering(self):
        ctx = self._make_ctx({"molecule": "water"})
        result = molecular_visualization(ctx)
        atoms = result["result"]["atoms"]
        cx = sum(a["x"] for a in atoms) / len(atoms)
        cy = sum(a["y"] for a in atoms) / len(atoms)
        cz = sum(a["z"] for a in atoms) / len(atoms)
        assert abs(cx) < 0.01
        assert abs(cy) < 0.01
        assert abs(cz) < 0.01

    def test_unknown_element_defaults(self):
        """Unknown elements get default radius and color."""
        mock_atom = MagicMock()
        mock_atom.GetSymbol.return_value = "Xx"
        mock_pos = MagicMock(x=1.0, y=0.0, z=0.0)
        mock_conf = MagicMock()
        mock_conf.GetAtomPosition.return_value = mock_pos
        mock_mol = MagicMock()
        mock_mol.GetNumAtoms.return_value = 1
        mock_mol.GetConformer.return_value = mock_conf
        mock_mol.GetAtomWithIdx.return_value = mock_atom
        mock_chem = MagicMock()
        mock_chem.MolFromSmiles.return_value = mock_mol
        mock_chem.AddHs.return_value = mock_mol
        mock_rdkit = MagicMock()
        mock_rdkit.Chem = mock_chem
        ctx = self._make_ctx({"smiles": "C"})
        with patch.dict("sys.modules", {
            "rdkit": mock_rdkit,
            "rdkit.Chem": mock_chem,
            "rdkit.Chem.AllChem": MagicMock(),
        }):
            result = molecular_visualization(ctx)
        atoms = result["result"]["atoms"]
        assert atoms[0]["radius"] == 0.5
        assert atoms[0]["color"] == "#888888"
