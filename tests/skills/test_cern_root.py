"""Tests for cern_root skill with mocked uproot."""

from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.cern_root import cern_root


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(id="t", user_intent="t", objective="t", metadata=meta)
    )


class TestCernRootMocked:
    """cern_root with mocked uproot."""

    def _mock_uproot(self):
        tree = MagicMock()
        tree.num_entries = 100
        arr = MagicMock()
        arr.tolist.return_value = [1, 2, 3]
        tree.arrays.return_value = {"x": arr, "y": arr}

        file = MagicMock()

        class _FakeTTree:
            pass

        ttree_inst = _FakeTTree()
        file.items.return_value = [("events", ttree_inst)]
        file.__getitem__ = MagicMock(return_value=tree)

        uproot = MagicMock()
        uproot.open.return_value.__enter__ = MagicMock(return_value=file)
        uproot.open.return_value.__exit__ = MagicMock(return_value=False)
        uproot.behaviors = MagicMock()
        uproot.behaviors.TTree = MagicMock()
        uproot.behaviors.TTree.TTree = _FakeTTree

        return uproot

    def test_read_tree_auto(self):
        uproot = self._mock_uproot()
        with patch.dict("sys.modules", {"uproot": uproot}):
            with patch(
                "uar.skills.cern_root.require_package",
                return_value=None,
            ):
                result = cern_root(
                    _ctx({
                        "root_file_path": "/tmp/test.root",
                        "root_tree_name": "events",
                    })
                )
        assert result["status"] == "completed"
        assert result["file"] == "/tmp/test.root"
        assert "branches" in result

    def test_read_tree_named(self):
        uproot = self._mock_uproot()
        with patch.dict("sys.modules", {"uproot": uproot}):
            with patch(
                "uar.skills.cern_root.require_package",
                return_value=None,
            ):
                result = cern_root(
                    _ctx({
                        "root_file_path": "/tmp/test.root",
                        "root_tree_name": "events",
                        "root_branches": ["x"],
                    })
                )
        assert result["status"] == "completed"

    def test_missing_file_path(self):
        uproot = self._mock_uproot()
        with patch.dict("sys.modules", {"uproot": uproot}):
            with patch(
                "uar.skills.cern_root.require_package",
                return_value=None,
            ):
                result = cern_root(_ctx({}))
        assert result["status"] == "failed"
        assert "root_file_path" in result["error"]

    def test_auto_discover_tree(self):
        uproot = self._mock_uproot()
        with patch.dict("sys.modules", {"uproot": uproot}):
            with patch(
                "uar.skills.cern_root.require_package",
                return_value=None,
            ):
                result = cern_root(
                    _ctx({"root_file_path": "/tmp/test.root"})
                )
        assert result["status"] == "completed"
        assert result["tree"] == "events"

    def test_no_ttree_found(self):
        uproot = self._mock_uproot()
        file = uproot.open.return_value.__enter__.return_value
        file.items.return_value = [("not_a_tree", "string")]
        with patch.dict("sys.modules", {"uproot": uproot}):
            with patch(
                "uar.skills.cern_root.require_package",
                return_value=None,
            ):
                result = cern_root(
                    _ctx({"root_file_path": "/tmp/test.root"})
                )
        assert result["status"] == "failed"
        assert "no TTree" in result["error"]

    def test_array_without_tolist(self):
        uproot = self._mock_uproot()
        tree = uproot.open.return_value.__enter__.return_value.__getitem__(
            "events"
        )
        arr_no_tolist = MagicMock()
        del arr_no_tolist.tolist  # no tolist attribute
        tree.arrays.return_value = {"x": arr_no_tolist}
        with patch.dict("sys.modules", {"uproot": uproot}):
            with patch(
                "uar.skills.cern_root.require_package",
                return_value=None,
            ):
                result = cern_root(
                    _ctx({
                        "root_file_path": "/tmp/test.root",
                        "root_tree_name": "events",
                    })
                )
        assert result["status"] == "completed"

    def test_uproot_raises(self):
        uproot = self._mock_uproot()
        uproot.open.side_effect = RuntimeError("file missing")
        with patch.dict("sys.modules", {"uproot": uproot}):
            with patch(
                "uar.skills.cern_root.require_package",
                return_value=None,
            ):
                result = cern_root(
                    _ctx({"root_file_path": "/tmp/test.root"})
                )
        assert result["status"] == "failed"

    def test_missing_dependency(self):
        with patch(
            "uar.skills.cern_root.require_package",
            return_value={"status": "failed", "error": "uproot missing"},
        ):
            result = cern_root(
                _ctx({"root_file_path": "/tmp/test.root"})
            )
        assert result["status"] == "failed"
