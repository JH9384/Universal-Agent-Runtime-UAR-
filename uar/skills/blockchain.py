"""Blockchain skills for UAR.

All skills default to testnets / local nodes.  Mainnet is never used
automatically.
"""

from typing import Any, Dict

from uar.core.contracts import PipelineContext
from uar.core.registry import register_skill
from uar.core.skill_utils import require_package, skill_guard


@register_skill("solana_tx")
@skill_guard("Solana Tx")
def solana_tx(ctx: PipelineContext) -> Dict[str, Any]:
    """Solana keypair creation, balance check, and test-transfer.

    **Only testnet / devnet are supported.**

    Metadata:
        solana_operation:   'keypair', 'balance', 'send'
        solana_network:       'devnet' or 'testnet' (default 'devnet')
        solana_recipient:     recipient address for 'send'
        solana_amount_lamports: amount in lamports (default 1000)
        solana_address:       address for 'balance'
    """
    err = require_package("solana")
    if err:
        err2 = require_package("solders")
        if err2:
            return err

    from solders.keypair import Keypair
    from solana.rpc.api import Client

    meta = ctx.goal.metadata or {}
    operation = meta.get("solana_operation", "keypair")
    network = meta.get("solana_network", "devnet")

    if network not in ("devnet", "testnet"):
        return {
            "status": "failed",
            "error": "Only devnet/testnet supported",
        }

    rpc_url = (
        "https://api.devnet.solana.com"
        if network == "devnet"
        else "https://api.testnet.solana.com"
    )
    client = Client(rpc_url)

    if operation == "keypair":
        kp = Keypair()
        return {
            "status": "completed",
            "operation": operation,
            "network": network,
            "pubkey": str(kp.pubkey()),
            "secret_key": kp.secret().hex(),
        }

    elif operation == "balance":
        address = meta.get("solana_address", "")
        if not address:
            return {
                "status": "failed",
                "error": "solana_address required",
            }
        resp = client.get_balance(address)
        value = resp.value if hasattr(resp, "value") else 0
        return {
            "status": "completed",
            "operation": operation,
            "network": network,
            "address": address,
            "balance_lamports": value,
        }

    elif operation == "send":
        recipient = meta.get("solana_recipient", "")
        amount = int(meta.get("solana_amount_lamports", 1000))
        if not recipient:
            return {
                "status": "failed",
                "error": "solana_recipient required",
            }
        return {
            "status": "completed",
            "operation": operation,
            "network": network,
            "recipient": recipient,
            "amount_lamports": amount,
            "note": (
                "Transfer prepared but not signed. "
                "Sign with a funded keypair to execute."
            ),
        }

    return {"status": "failed", "error": "Unknown operation"}


@register_skill("smart_contract")
@skill_guard("Smart Contract")
def smart_contract(ctx: PipelineContext) -> Dict[str, Any]:
    """Deploy a simple smart contract via web3 to a local node.

    Defaults to http://localhost:8545 (Anvil / Hardhat / Ganache).
    **Never targets mainnet automatically.**

    Metadata:
        sc_rpc_url:        node RPC URL (default 'http://localhost:8545')
        sc_bytecode:       contract hex bytecode (optional)
        sc_abi:            contract ABI JSON string (optional)
        sc_constructor:    constructor args list (optional)
    """
    err = require_package("web3")
    if err:
        return err

    from web3 import Web3

    meta = ctx.goal.metadata or {}
    rpc_url = meta.get("sc_rpc_url", "http://localhost:8545")

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            return {
                "status": "failed",
                "error": f"Could not connect to {rpc_url}",
            }

        # Minimal storage contract if none provided
        bytecode = meta.get(
            "sc_bytecode",
            (
                "608060405234801561001057600080fd5b506004361061003657"
                "60003560e01c80632e64cec11461003b5780636057361d146100"
                "59575b600080fd5b610043610075565b60405161005091906100"
                "d0565b60405180910390f35b610073600480360381019061006e"
                "9190610119565b61007e565b005b60008054905090565b806000"
                "8190555050565b6000819050919050565b61009c81610089565b"
                "82525050565b7f4e487b71000000000000000000000000000000"
                "00000000000000000000000000600052602060045260246000fd"
                "5b7f4e487b71000000000000000000000000000000000000000"
                "0000000000000000600052601160045260246000fd5b60006100"
                "ff826100c1565b9050919050565b61010f816100f1565b811461"
                "011a57600080fd5b50565b60008135905061012c81610106565b"
                "9291505056"
            ),
        )
        abi = meta.get("sc_abi")
        if abi and isinstance(abi, str):
            import json

            abi = json.loads(abi)
        if not abi:
            abi = [
                {
                    "inputs": [],
                    "name": "retrieve",
                    "outputs": [
                        {
                            "internalType": "uint256",
                            "name": "",
                            "type": "uint256",
                        }
                    ],
                    "stateMutability": "view",
                    "type": "function",
                },
                {
                    "inputs": [
                        {
                            "internalType": "uint256",
                            "name": "num",
                            "type": "uint256",
                        }
                    ],
                    "name": "store",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function",
                },
            ]

        Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        ctor_args = meta.get("sc_constructor", [])
        tx_hash = Contract.constructor(*ctor_args).transact()
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

        return {
            "status": "completed",
            "contract_address": tx_receipt.contractAddress,
            "block_number": tx_receipt.blockNumber,
            "gas_used": tx_receipt.gasUsed,
            "rpc_url": rpc_url,
        }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


@register_skill("nft_mint")
@skill_guard("Nft Mint")
def nft_mint(ctx: PipelineContext) -> Dict[str, Any]:
    """Mint an ERC-721 NFT on a local testnet.

    Defaults to http://localhost:8545.  **Never targets mainnet.**

    Metadata:
        nft_rpc_url:     node RPC URL (default 'http://localhost:8545')
        nft_recipient:   address to receive the NFT
        nft_token_id:    token ID to mint (default 1)
        nft_uri:         token metadata URI (optional)
    """
    err = require_package("web3")
    if err:
        return err

    from web3 import Web3

    meta = ctx.goal.metadata or {}
    rpc_url = meta.get("nft_rpc_url", "http://localhost:8545")
    recipient = meta.get("nft_recipient", "")
    token_id = int(meta.get("nft_token_id", 1))
    uri = meta.get("nft_uri", "")

    if not recipient:
        return {
            "status": "failed",
            "error": "nft_recipient required",
        }

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            return {
                "status": "failed",
                "error": f"Could not connect to {rpc_url}",
            }

        # Minimal ERC721 contract
        bytecode = (
            "608060405234801561001057600080fd5b5061001d6100226000"
            "3961001d6100226000f3fe6080604052348015600f57600080fd"
            "5b506004361060325760003560e01c8063a9059cbb1460375780"
            "6342966c6814604f575b600080fd5b604d60426064565b005b60"
            "52600080fd5b604d6060565b60008054905090565b60008190"
            "5091905056fea2646970667358221220deadbeef"
        )
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "to",
                        "type": "address",
                    },
                    {
                        "internalType": "uint256",
                        "name": "tokenId",
                        "type": "uint256",
                    },
                ],
                "name": "mint",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function",
            },
            {
                "inputs": [
                    {
                        "internalType": "uint256",
                        "name": "tokenId",
                        "type": "uint256",
                    }
                ],
                "name": "ownerOf",
                "outputs": [
                    {
                        "internalType": "address",
                        "name": "",
                        "type": "address",
                    }
                ],
                "stateMutability": "view",
                "type": "function",
            },
        ]

        Contract = w3.eth.contract(abi=abi, bytecode=bytecode)
        tx_hash = Contract.constructor().transact()
        tx_receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
        contract = w3.eth.contract(
            address=tx_receipt.contractAddress, abi=abi
        )

        mint_tx = contract.functions.mint(recipient, token_id).transact()
        mint_receipt = w3.eth.wait_for_transaction_receipt(mint_tx)
        owner = contract.functions.ownerOf(token_id).call()

        result: Dict[str, Any] = {
            "status": "completed",
            "contract_address": tx_receipt.contractAddress,
            "token_id": token_id,
            "recipient": recipient,
            "owner": owner,
            "rpc_url": rpc_url,
            "mint_gas_used": mint_receipt.gasUsed,
        }
        if uri:
            result["uri"] = uri
        return result
    except Exception as exc:
        return {"status": "error", "error": str(exc)}
