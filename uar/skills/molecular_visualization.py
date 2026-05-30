"""Molecular structure visualization skill.

Generates 3D atomic coordinates and bond topology for molecular
structures.  Supports common molecules and custom SMILES input.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext


# Common molecule structures (simplified coordinates in Angstroms)
_MOLECULES: Dict[str, List[Dict[str, Any]]] = {
    "water": [
        {"element": "O", "x": 0.0, "y": 0.0, "z": 0.0},
        {"element": "H", "x": 0.757, "y": 0.586, "z": 0.0},
        {"element": "H", "x": -0.757, "y": 0.586, "z": 0.0},
    ],
    "methane": [
        {"element": "C", "x": 0.0, "y": 0.0, "z": 0.0},
        {"element": "H", "x": 0.63, "y": 0.63, "z": 0.63},
        {"element": "H", "x": -0.63, "y": -0.63, "z": 0.63},
        {"element": "H", "x": -0.63, "y": 0.63, "z": -0.63},
        {"element": "H", "x": 0.63, "y": -0.63, "z": -0.63},
    ],
    "benzene": [
        {"element": "C", "x": 1.39, "y": 0.0, "z": 0.0},
        {"element": "C", "x": 0.695, "y": 1.204, "z": 0.0},
        {"element": "C", "x": -0.695, "y": 1.204, "z": 0.0},
        {"element": "C", "x": -1.39, "y": 0.0, "z": 0.0},
        {"element": "C", "x": -0.695, "y": -1.204, "z": 0.0},
        {"element": "C", "x": 0.695, "y": -1.204, "z": 0.0},
        {"element": "H", "x": 2.47, "y": 0.0, "z": 0.0},
        {"element": "H", "x": 1.235, "y": 2.14, "z": 0.0},
        {"element": "H", "x": -1.235, "y": 2.14, "z": 0.0},
        {"element": "H", "x": -2.47, "y": 0.0, "z": 0.0},
        {"element": "H", "x": -1.235, "y": -2.14, "z": 0.0},
        {"element": "H", "x": 1.235, "y": -2.14, "z": 0.0},
    ],
    "caffeine": [
        {"element": "C", "x": 0.0, "y": 0.0, "z": 0.0},
        {"element": "N", "x": 1.4, "y": 0.0, "z": 0.0},
        {"element": "C", "x": 2.1, "y": 1.2, "z": 0.0},
        {"element": "N", "x": 1.4, "y": 2.4, "z": 0.0},
        {"element": "C", "x": 0.0, "y": 2.4, "z": 0.0},
        {"element": "C", "x": -0.7, "y": 1.2, "z": 0.0},
        {"element": "O", "x": -0.7, "y": -1.2, "z": 0.0},
        {"element": "N", "x": 0.7, "y": -1.2, "z": 0.0},
        {"element": "C", "x": 2.8, "y": -0.6, "z": 0.0},
        {"element": "C", "x": 3.5, "y": 1.2, "z": 0.0},
    ],
}

_ATOMIC_RADII: Dict[str, float] = {
    "H": 0.31,
    "C": 0.76,
    "N": 0.71,
    "O": 0.66,
    "F": 0.57,
    "P": 1.07,
    "S": 1.05,
    "Cl": 1.02,
}

_ELEMENT_COLORS: Dict[str, str] = {
    "H": "#ffffff",
    "C": "#333333",
    "N": "#3050f8",
    "O": "#ff0d0d",
    "F": "#90e050",
    "P": "#ff8000",
    "S": "#ffff30",
    "Cl": "#1ff01f",
}


def _compute_bonds(
    atoms: List[Dict[str, Any]],
) -> List[Tuple[int, int, float]]:
    """Compute covalent bonds based on distance threshold."""
    bonds: List[Tuple[int, int, float]] = []
    threshold_scale = 1.3  # Bond if within 130% of sum of covalent radii
    for i in range(len(atoms)):
        for j in range(i + 1, len(atoms)):
            a1 = atoms[i]
            a2 = atoms[j]
            r1 = _ATOMIC_RADII.get(a1["element"], 0.5)
            r2 = _ATOMIC_RADII.get(a2["element"], 0.5)
            dx = a1["x"] - a2["x"]
            dy = a1["y"] - a2["y"]
            dz = a1["z"] - a2["z"]
            dist = math.sqrt(dx * dx + dy * dy + dz * dz)
            if dist < (r1 + r2) * threshold_scale:
                bonds.append((i, j, dist))
    return bonds


def _generate_protein_backbone(
    residues: int = 10,
) -> List[Dict[str, Any]]:
    """Generate a simple alpha-helix backbone."""
    atoms: List[Dict[str, Any]] = []
    r = 2.3  # Helix radius in Angstroms
    rise = 1.5  # Rise per residue
    for i in range(residues):
        t = i * math.radians(100)  # 100 degrees per residue
        x = r * math.cos(t)
        y = r * math.sin(t)
        z = i * rise
        # N-CA-C backbone atoms
        atoms.append({
            "element": "N", "x": x, "y": y, "z": z - 0.5,
        })
        atoms.append({
            "element": "C", "x": x + 0.5, "y": y, "z": z,
        })
        atoms.append({
            "element": "C", "x": x + 1.2,
            "y": y + 0.3, "z": z + 0.5,
        })
        # Oxygen on carbonyl
        atoms.append({
            "element": "O", "x": x + 1.8,
            "y": y + 0.3, "z": z + 0.8,
        })
    return atoms


def _parse_smiles_basic(smiles: str) -> List[Dict[str, Any]]:
    """Basic SMILES parser for common atoms (no ring closures, no stereo).

    Falls back when RDKit is not installed.  Recognizes:
    - Element symbols: C, N, O, S, P, F, Cl, Br, I, H
    - Aromatic lower-case: c, n, o, s
    - Single bonds (implicit), double (=), triple (#)
    - Branches in parentheses
    """
    atoms: List[Dict[str, Any]] = []
    # Simple linear layout: place atoms along X axis with random-ish
    # Y/Z offsets so bonds don't perfectly overlap.
    idx = 0
    i = 0
    bond_lengths = {"-": 1.54, "=": 1.34, "#": 1.20}
    current_bond = "-"
    x = 0.0
    while i < len(smiles):
        ch = smiles[i]
        # Two-letter symbols
        if i + 1 < len(smiles) and smiles[i:i + 2] in ("Cl", "Br"):
            el = smiles[i:i + 2]
            i += 2
        elif ch == "c":
            el = "C"
            i += 1
        elif ch == "n":
            el = "N"
            i += 1
        elif ch == "o":
            el = "O"
            i += 1
        elif ch == "s":
            el = "S"
            i += 1
        elif ch.upper() in "CNOPSFIH" and ch.isalpha():
            el = ch.upper()
            i += 1
        elif ch in "=-#":
            current_bond = ch
            i += 1
            continue
        elif ch in "()[]":
            i += 1
            continue
        elif ch.isdigit():
            i += 1
            continue
        else:
            i += 1
            continue

        bl = bond_lengths.get(current_bond, 1.54)
        # Add small random offset in Y/Z for visual separation
        y = (idx % 3 - 1) * 0.3
        z = (idx % 2 - 0.5) * 0.2
        atoms.append({"element": el, "x": x, "y": y, "z": z})
        x += bl
        idx += 1
        current_bond = "-"
    return atoms


def _rdkit_generate(smiles: str) -> List[Dict[str, Any]] | None:
    """Use RDKit to generate accurate 3D coordinates from SMILES."""
    try:
        from rdkit import Chem
        from rdkit.Chem import AllChem
    except ImportError:
        return None

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    mol = Chem.AddHs(mol)
    AllChem.EmbedMolecule(mol, AllChem.ETKDG())
    AllChem.MMFFOptimizeMolecule(mol)
    conformer = mol.GetConformer()
    atoms: List[Dict[str, Any]] = []
    for i in range(mol.GetNumAtoms()):
        atom = mol.GetAtomWithIdx(i)
        pos = conformer.GetAtomPosition(i)
        atoms.append({
            "element": atom.GetSymbol(),
            "x": pos.x,
            "y": pos.y,
            "z": pos.z,
        })
    return atoms


def molecular_visualization(
    ctx: PipelineContext,
) -> Dict[str, Any]:
    """Generate 3D molecular structure data for visualization.

    Parameters (from ctx.goal.metadata):
        molecule: str - molecule name (water, methane, benzene, caffeine)
            or "protein" for backbone
        smiles: str - SMILES string (takes priority over molecule name)
        residues: int - for protein backbone (default: 10)
    """
    params = ctx.goal.metadata or {}
    molecule = str(params.get("molecule", "water"))
    residues = int(params.get("residues", 10))
    smiles = str(params.get("smiles", "")).strip()

    if smiles:
        # Try RDKit first for accurate geometry
        atoms = _rdkit_generate(smiles)
        if atoms is None:
            atoms = _parse_smiles_basic(smiles)
        source = "smiles"
    elif molecule == "protein":
        atoms = _generate_protein_backbone(residues)
        source = "protein_backbone"
    else:
        atoms = _MOLECULES.get(molecule, _MOLECULES["water"])
        source = "hardcoded"

    bonds = _compute_bonds(atoms)

    # Center the molecule
    cx = sum(a["x"] for a in atoms) / len(atoms)
    cy = sum(a["y"] for a in atoms) / len(atoms)
    cz = sum(a["z"] for a in atoms) / len(atoms)

    centered = [
        {
            "element": a["element"],
            "x": a["x"] - cx,
            "y": a["y"] - cy,
            "z": a["z"] - cz,
            "radius": _ATOMIC_RADII.get(a["element"], 0.5),
            "color": _ELEMENT_COLORS.get(a["element"], "#888888"),
        }
        for a in atoms
    ]

    return {
        "status": "completed",
        "goal": ctx.goal.user_intent,
        "result": {
            "atoms": centered,
            "bonds": bonds,
            "molecule": molecule,
            "smiles": smiles,
            "source": source,
            "atom_count": len(atoms),
            "bond_count": len(bonds),
        },
        "metrics": {
            "atoms": len(atoms),
            "bonds": len(bonds),
        },
    }


register_skill("molecular_visualization")(molecular_visualization)
