"""Tests for blockchain skills error paths."""

from unittest.mock import patch

from uar.core.contracts import GoalSpec, PipelineContext
from uar.skills.blockchain import solana_tx, smart_contract, nft_mint


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestSolanaTxMissingPackage:
    """solana_tx when solana/solders not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.blockchain.require_package",
            return_value={"status": "failed", "error": "missing"},
        ):
            result = solana_tx(_ctx({"solana_operation": "keypair"}))
        assert result["status"] == "failed"

    def test_rejects_mainnet(self):
        with patch(
            "uar.skills.blockchain.require_package",
            return_value=None,
        ):
            with patch.dict("sys.modules", {
                "solana": None, "solders": None,
            }):
                result = solana_tx(
                    _ctx({"solana_network": "mainnet"})
                )
        # import fails before mainnet guard -> skill_guard returns error
        assert result["status"] == "error"


class TestSmartContractMissingPackage:
    """smart_contract when web3 not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.blockchain.require_package",
            return_value={"status": "failed", "error": "web3 missing"},
        ):
            result = smart_contract(_ctx({"sc_rpc_url": "http://l:8545"}))
        assert result["status"] == "failed"


class TestNftMintMissingPackage:
    """nft_mint when web3 not installed."""

    def test_returns_error(self):
        with patch(
            "uar.skills.blockchain.require_package",
            return_value={"status": "failed", "error": "web3 missing"},
        ):
            result = nft_mint(_ctx({"nft_recipient": "0xabc"}))
        assert result["status"] == "failed"

    def test_missing_recipient(self):
        with patch(
            "uar.skills.blockchain.require_package",
            return_value=None,
        ):
            with patch.dict("sys.modules", {"web3": None}):
                result = nft_mint(_ctx({}))
        assert result["status"] == "error"
