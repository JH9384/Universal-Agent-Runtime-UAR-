"""CERN ROOT file reader skill using uproot.

Reads .root files, extracts TTree data, and returns structured output.
"""

from typing import Any, Dict

from uar.core.registry import register_skill
from uar.core.contracts import PipelineContext
from uar.core.skill_utils import require_package, skill_guard


@register_skill("cern_root")
@skill_guard("Cern Root")
def cern_root(ctx: PipelineContext) -> Dict[str, Any]:
    """Read CERN ROOT files with uproot.

    Metadata:
        root_file_path: path to the .root file
        root_tree_name: name of the TTree to read (optional)
        root_branches:  list of branch names to extract (optional)
        root_entry_stop: max entries to read (optional)
    """
    err = require_package("uproot", install_hint="pip install uproot")
    if err:
        return err

    import uproot

    meta = ctx.goal.metadata or {}
    file_path = meta.get("root_file_path", "")
    if not file_path:
        return {"status": "failed", "error": "root_file_path required"}

    try:
        with uproot.open(file_path) as file:
            tree_name = meta.get("root_tree_name")
            if tree_name is None:
                trees = [
                    k for k, v in file.items()
                    if isinstance(v, uproot.behaviors.TTree.TTree)
                ]
                if not trees:
                    return {
                        "status": "failed",
                        "error": "no TTree found in file",
                    }
                tree_name = trees[0]

            tree = file[tree_name]
            branches = meta.get("root_branches")
            entry_stop = meta.get("root_entry_stop")

            arrays = tree.arrays(
                branches,
                entry_stop=entry_stop,
                library="np",
            )

            data = {}
            for key, arr in arrays.items():
                if hasattr(arr, "tolist"):
                    data[key] = arr.tolist()
                else:
                    data[key] = arr

            return {
                "status": "completed",
                "file": file_path,
                "tree": tree_name,
                "num_entries": int(tree.num_entries),
                "branches": list(data.keys()),
                "data": data,
            }
    except Exception as exc:
        return {"status": "failed", "error": str(exc)}
