"""Tests for blockchain skills with mocked heavy deps."""

import types
from unittest.mock import MagicMock, patch

from uar.core.contracts import GoalSpec, PipelineContext


def _ctx(meta: dict) -> PipelineContext:
    return PipelineContext(
        goal=GoalSpec(
            id="t", user_intent="t", objective="t", metadata=meta
        )
    )


class TestSolanaTxMocked:
    """solana_tx with mocked solana libs."""

    def test_keypair(self):
        mock_kp = MagicMock()
        mock_kp.pubkey.return_value = "FakePubkey123"
        mock_kp.secret.return_value = b"\x00" * 32
        mock_keypair = MagicMock()
        mock_keypair.return_value = mock_kp

        mock_client = MagicMock()
        mock_solana = types.ModuleType("solana.rpc.api")
        mock_solana.Client = mock_client
        mock_solders = types.ModuleType("solders.keypair")
        mock_solders.Keypair = mock_keypair

        with patch.dict("sys.modules", {
            "solana": MagicMock(),
            "solana.rpc": MagicMock(),
            "solana.rpc.api": mock_solana,
            "solders": MagicMock(),
            "solders.keypair": mock_solders,
        }):
            with patch(
                "uar.skills.blockchain.require_package",
                return_value=None,
            ):
                from uar.skills.blockchain import solana_tx
                result = solana_tx(
                    _ctx({"solana_operation": "keypair"})
                )
        assert result["status"] == "completed"
        assert result["operation"] == "keypair"
        assert result["pubkey"] == "FakePubkey123"

    def test_balance(self):
        mock_resp = MagicMock()
        mock_resp.value = 500000000
        mock_client = MagicMock()
        mock_client.return_value.get_balance.return_value = mock_resp
        mock_solana = types.ModuleType("solana.rpc.api")
        mock_solana.Client = mock_client

        with patch.dict("sys.modules", {
            "solana": MagicMock(),
            "solana.rpc": MagicMock(),
            "solana.rpc.api": mock_solana,
            "solders": MagicMock(),
            "solders.keypair": MagicMock(),
        }):
            with patch(
                "uar.skills.blockchain.require_package",
                return_value=None,
            ):
                from uar.skills.blockchain import solana_tx
                result = solana_tx(
                    _ctx({
                        "solana_operation": "balance",
                        "solana_address": "FakeAddress",
                    })
                )
        assert result["status"] == "completed"
        assert result["balance_lamports"] == 500000000

    def test_send(self):
        mock_client = MagicMock()
        mock_solana = types.ModuleType("solana.rpc.api")
        mock_solana.Client = mock_client

        with patch.dict("sys.modules", {
            "solana": MagicMock(),
            "solana.rpc": MagicMock(),
            "solana.rpc.api": mock_solana,
            "solders": MagicMock(),
            "solders.keypair": MagicMock(),
        }):
            with patch(
                "uar.skills.blockchain.require_package",
                return_value=None,
            ):
                from uar.skills.blockchain import solana_tx
                result = solana_tx(
                    _ctx({
                        "solana_operation": "send",
                        "solana_recipient": "Recip",
                        "solana_amount_lamports": 2000,
                    })
                )
        assert result["status"] == "completed"
        assert result["amount_lamports"] == 2000


class TestSmartContractMocked:
    """smart_contract with mocked web3."""

    def test_deploy(self):
        mock_tx_receipt = MagicMock()
        mock_tx_receipt.contractAddress = "0xContractAddr"
        mock_tx_receipt.blockNumber = 42
        mock_tx_receipt.gasUsed = 123456

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.wait_for_transaction_receipt.return_value = mock_tx_receipt
        mock_w3.eth.contract.return_value.constructor.return_value.transact.return_value = "0xtxhash"  # noqa: E501

        mock_cls = MagicMock()
        mock_cls.HTTPProvider = MagicMock()
        mock_cls.return_value = mock_w3

        mock_mod = types.ModuleType("web3")
        mock_mod.Web3 = mock_cls

        with patch.dict("sys.modules", {"web3": mock_mod}):
            with patch(
                "uar.skills.blockchain.require_package",
                return_value=None,
            ):
                from uar.skills.blockchain import smart_contract
                result = smart_contract(
                    _ctx({"sc_rpc_url": "http://localhost:8545"})
                )
        assert result["status"] == "completed"
        assert result["contract_address"] == "0xContractAddr"
        assert result["rpc_url"] == "http://localhost:8545"

    def test_connection_fail(self):
        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = False

        mock_cls = MagicMock()
        mock_cls.HTTPProvider = MagicMock()
        mock_cls.return_value = mock_w3

        mock_mod = types.ModuleType("web3")
        mock_mod.Web3 = mock_cls

        with patch.dict("sys.modules", {"web3": mock_mod}):
            with patch(
                "uar.skills.blockchain.require_package",
                return_value=None,
            ):
                from uar.skills.blockchain import smart_contract
                result = smart_contract(
                    _ctx({"sc_rpc_url": "http://dead:8545"})
                )
        assert result["status"] == "failed"


class TestNftMintMocked:
    """nft_mint with mocked web3."""

    def test_mint(self):
        mock_tx_receipt = MagicMock()
        mock_tx_receipt.contractAddress = "0xNftContract"
        mock_tx_receipt.gasUsed = 98765

        mock_contract = MagicMock()
        mock_contract.functions.mint.return_value.transact.return_value = "0xminthash"  # noqa: E501
        mock_contract.functions.ownerOf.return_value.call.return_value = (
            "0xRecipient"
        )

        mock_w3 = MagicMock()
        mock_w3.is_connected.return_value = True
        mock_w3.eth.wait_for_transaction_receipt.return_value = mock_tx_receipt
        # First call: deploy contract (constructor), second: at address
        mock_w3.eth.contract.side_effect = [
            mock_contract,  # deploy
            mock_contract,  # at address
        ]

        mock_cls = MagicMock()
        mock_cls.HTTPProvider = MagicMock()
        mock_cls.return_value = mock_w3

        mock_mod = types.ModuleType("web3")
        mock_mod.Web3 = mock_cls

        with patch.dict("sys.modules", {"web3": mock_mod}):
            with patch(
                "uar.skills.blockchain.require_package",
                return_value=None,
            ):
                from uar.skills.blockchain import nft_mint
                result = nft_mint(
                    _ctx({
                        "nft_recipient": "0xRecipient",
                        "nft_token_id": 1,
                        "nft_uri": "ipfs://test",
                    })
                )
        assert result["status"] == "completed"
        assert result["token_id"] == 1
        assert result["owner"] == "0xRecipient"
        assert result["uri"] == "ipfs://test"

    def test_missing_recipient(self):
        with patch(
            "uar.skills.blockchain.require_package",
            return_value=None,
        ):
            with patch.dict("sys.modules", {"web3": None}):
                from uar.skills.blockchain import nft_mint
                result = nft_mint(_ctx({}))
        assert result["status"] == "error"
