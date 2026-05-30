"""Tests for uar.skills.uor_ecosystem_skills."""

from unittest.mock import MagicMock, patch

from uar.skills.uor_ecosystem_skills import (
    uor_addr_canonicalize,
    uor_addr_resolve,
    hologram_query,
    hologram_status,
    moltbook_list,
    moltbook_search,
    moltbook_post,
    prism_btc_anchor,
    prism_btc_verify,
    severance_infer,
    severance_verify,
    anunix_health,
    anunix_run,
    uor_foundation_verify,
    uor_ecosystem_status,
)


def _make_ctx(metadata=None):
    ctx = MagicMock()
    ctx.goal.metadata = metadata or {}
    return ctx


def _mock_eco():
    eco = MagicMock()
    uor_obj = MagicMock()
    uor_obj.digest = "sha256:abc"
    uor_obj.size = 10
    uor_obj.data = {"test": 1}
    uor_obj.media_type = "application/json"
    uor_obj.provenance = []
    eco.uor_addr.canonicalize.return_value = {"digest": "d1"}
    eco.uor_addr.wrap_with_uor.return_value = uor_obj
    eco.uor_addr.resolve.return_value = uor_obj
    eco.hologram.query.return_value = {"result": "ok"}
    eco.hologram.status.return_value = {"healthy": True}
    eco.moltbook.list_topics.return_value = {"topics": []}
    eco.moltbook.search.return_value = {"results": []}
    eco.moltbook.post_topic.return_value = {"id": "p1"}
    eco.prism_btc.anchor_digest.return_value = {"txid": "t1"}
    eco.prism_btc.verify_anchor.return_value = {"valid": True}
    eco.severance_ai.infer.return_value = {"output": "hello"}
    eco.severance_ai.verify_output.return_value = {"valid": True}
    eco.anunix.health_check.return_value = {"status": "up"}
    eco.anunix.run_command.return_value = {"stdout": "out"}
    eco.uor_foundation.verify.return_value = {"verified": True}
    return eco


class TestUorAddr:
    def test_canonicalize_no_data(self):
        ctx = _make_ctx()
        result = uor_addr_canonicalize(ctx)
        assert result["status"] == "failed"

    def test_canonicalize_success(self):
        ctx = _make_ctx({"data": {"a": 1}})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = uor_addr_canonicalize(ctx)
        assert result["status"] == "completed"
        assert result["uor_digest"] == "sha256:abc"

    def test_resolve_no_digest(self):
        ctx = _make_ctx()
        result = uor_addr_resolve(ctx)
        assert result["status"] == "failed"

    def test_resolve_not_found(self):
        ctx = _make_ctx({"digest": "sha256:missing"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            eco = _mock_eco()
            eco.uor_addr.resolve.return_value = None
            get_eco.return_value = eco
            result = uor_addr_resolve(ctx)
        assert result["status"] == "failed"

    def test_resolve_success(self):
        ctx = _make_ctx({"digest": "sha256:abc"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = uor_addr_resolve(ctx)
        assert result["status"] == "completed"


class TestHologram:
    def test_query(self):
        ctx = _make_ctx({"model_id": "m1", "inputs": {"x": 1}})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = hologram_query(ctx)
        assert result["status"] == "completed"

    def test_status(self):
        ctx = _make_ctx()
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = hologram_status(ctx)
        assert result["status"] == "completed"


class TestMoltbook:
    def test_list(self):
        ctx = _make_ctx()
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = moltbook_list(ctx)
        assert result["status"] == "completed"

    def test_search_no_query(self):
        ctx = _make_ctx()
        result = moltbook_search(ctx)
        assert result["status"] == "failed"

    def test_search(self):
        ctx = _make_ctx({"query": "hello"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = moltbook_search(ctx)
        assert result["status"] == "completed"

    def test_post_missing(self):
        ctx = _make_ctx({"title": "t"})
        result = moltbook_post(ctx)
        assert result["status"] == "failed"

    def test_post(self):
        ctx = _make_ctx({"title": "t", "body": "b"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = moltbook_post(ctx)
        assert result["status"] == "completed"


class TestPrismBtc:
    def test_anchor_no_digest(self):
        ctx = _make_ctx()
        result = prism_btc_anchor(ctx)
        assert result["status"] == "failed"

    def test_anchor(self):
        ctx = _make_ctx({"digest": "sha256:abc"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = prism_btc_anchor(ctx)
        assert result["status"] == "completed"

    def test_verify_no_digest(self):
        ctx = _make_ctx()
        result = prism_btc_verify(ctx)
        assert result["status"] == "failed"

    def test_verify(self):
        ctx = _make_ctx({"digest": "sha256:abc"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = prism_btc_verify(ctx)
        assert result["status"] == "completed"


class TestSeverance:
    def test_infer_no_prompt(self):
        ctx = _make_ctx()
        result = severance_infer(ctx)
        assert result["status"] == "failed"

    def test_infer(self):
        ctx = _make_ctx({"prompt": "hello"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = severance_infer(ctx)
        assert result["status"] == "completed"

    def test_verify_no_output(self):
        ctx = _make_ctx()
        result = severance_verify(ctx)
        assert result["status"] == "failed"

    def test_verify(self):
        ctx = _make_ctx({"output": "hello"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = severance_verify(ctx)
        assert result["status"] == "completed"


class TestAnunix:
    def test_health_no_host(self):
        ctx = _make_ctx()
        result = anunix_health(ctx)
        assert result["status"] == "failed"

    def test_health(self):
        ctx = _make_ctx({"host_id": "h1"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            eco = _mock_eco()
            eco.anunix.health_check.return_value = {"online": True}
            get_eco.return_value = eco
            result = anunix_health(ctx)
        assert result["status"] == "completed"

    def test_run_missing(self):
        ctx = _make_ctx({"host_id": "h1"})
        result = anunix_run(ctx)
        assert result["status"] == "failed"

    def test_run(self):
        ctx = _make_ctx({"host_id": "h1", "command": "ls"})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = anunix_run(ctx)
        assert result["status"] == "completed"


class TestUorFoundation:
    def test_verify(self):
        ctx = _make_ctx({"x": 1})
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            get_eco.return_value = _mock_eco()
            result = uor_foundation_verify(ctx)
        assert result["status"] == "completed"


class TestEcosystemStatus:
    def test_status(self):
        ctx = _make_ctx()
        with patch(
            "uar.skills.uor_ecosystem_skills.get_uor_ecosystem"
        ) as get_eco:
            eco = _mock_eco()
            eco.status.return_value = {
                "uor_addr": True,
                "hologram": True,
                "moltbook": True,
                "prism_btc": True,
                "severance_ai": True,
                "anunix": True,
                "uor_foundation": True,
            }
            get_eco.return_value = eco
            result = uor_ecosystem_status(ctx)
        assert result["status"] == "completed"
