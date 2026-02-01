"""Higher-level tool implementations exposed to MCP."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from . import settings
from .utils.errors import ValidationError
from .tron_api import (
    fetch_account,
    fetch_chain_parameters,
    fetch_tx_info,
    fetch_tx_meta,
    fetch_transactions,
    fetch_trc20_transfers,
    fetch_transactions_tronscan,
    fetch_trc20_transfers_tronscan,
)
from .utils import format_token_amount, validate_address, validate_txid
from .utils.errors import UpstreamError


@dataclass
class Tool:
    name: str
    description: str
    inputSchema: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


TOOL_DEFINITIONS: List[Tool] = [
    Tool(
        name="get_usdt_balance",
        description="Fetch TRC20 USDT balance for an address (TRONSCAN).",
        inputSchema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "TRON Base58 address starting with T"}
            },
            "required": ["address"],
        },
    ),
    Tool(
        name="get_network_params",
        description="Get current TRON chain parameters (energy fee, bandwidth fee, account creation cost).",
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="get_tx_status",
        description="Check transaction confirmation status and receipt summary on TRON.",
        inputSchema={
            "type": "object",
            "properties": {"txid": {"type": "string", "description": "64-character hex hash"}},
            "required": ["txid"],
        },
    ),
    Tool(
        name="get_recent_transactions",
        description="List recent transactions for an address (in/out, brief summary).",
        inputSchema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "TRON Base58 address starting with T"},
                "limit": {"type": "integer", "description": "Max items, 1-50", "minimum": 1, "maximum": 50},
            },
            "required": ["address"],
        },
    ),
    Tool(
        name="get_trc20_transfers",
        description="List recent TRC20 transfers involving an address.",
        inputSchema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "TRON Base58 address starting with T"},
                "limit": {"type": "integer", "description": "Max items, 1-50", "minimum": 1, "maximum": 50},
            },
            "required": ["address"],
        },
    ),
    Tool(
        name="get_address_labels",
        description="Return basic labels/flags for an address (name, tags, contract flag).",
        inputSchema={
            "type": "object",
            "properties": {"address": {"type": "string", "description": "TRON Base58 address starting with T"}},
            "required": ["address"],
        },
    ),
]


def list_tools() -> Dict[str, Any]:
    """Return tool definitions for MCP list_tools."""
    return {"tools": [t.to_dict() for t in TOOL_DEFINITIONS]}


def get_usdt_balance(address: str) -> Dict[str, Any]:
    """Lookup TRC20 USDT balance via TRONSCAN payload fields."""
    validate_address(address)
    account = fetch_account(address)

    candidates = (
        account.get("trc20token_balances")
        or account.get("trc20token_balancesV2")
        or account.get("trc20")
        or account.get("tokenBalances")
        or []
    )

    usdt = None
    for token in candidates:
        contract = (
            token.get("tokenId")
            or token.get("contract_address")
            or token.get("tokenAddress")
            or token.get("token_id")
            or token.get("tokenIdAddress")
        )
        if contract and contract.upper() == settings.SETTINGS.usdt_contract.upper():
            usdt = token
            break

    balance_raw = "0"
    if usdt:
        for key in ("balance", "amount", "tokenBalance", "quantity"):
            candidate = usdt.get(key)
            if candidate not in (None, "", "0"):
                balance_raw = str(candidate)
                break
    decimals = int(usdt.get("tokenDecimal") or usdt.get("decimals") or 6) if usdt else 6

    return {
        "address": address,
        "contract": settings.SETTINGS.usdt_contract,
        "balance": {
            "raw": str(balance_raw),
            "human": format_token_amount(str(balance_raw), decimals),
            "decimals": decimals,
        },
        "source": "TRONSCAN",
        "apiUrl": f"{settings.SETTINGS.tronscan_base}/account?address={address}",
        "updated": account.get("updateTime") or account.get("date_updated"),
    }


def get_network_params() -> Dict[str, Any]:
    """Return chain fee parameters summarized in sun."""
    params = fetch_chain_parameters()
    table = {item.get("key"): item.get("value") for item in params.get("chainParameter", [])}

    return {
        "energyFeeSun": table.get("getEnergyFee"),
        "bandwidthFeeSun": table.get("getTransactionFee"),
        "createAccountFeeSun": table.get("getCreateAccountFee"),
        "memoFeePerByteSun": table.get("getMemoFee"),
        "notes": "Values are in sun (1 TRX = 1,000,000 sun).",
        "raw": params,
    }


def get_tx_status(txid: str) -> Dict[str, Any]:
    """Query tx existence and receipt, mapping to a concise status."""
    validate_txid(txid)

    meta = None
    info = None

    try:
        meta = fetch_tx_meta(txid)
    except Exception:
        meta = None
    try:
        info = fetch_tx_info(txid)
    except Exception:
        info = None

    status = "NOT_FOUND"
    if info and info.get("id"):
        result = (
            info.get("receipt", {}).get("result")
            or info.get("result")
            or info.get("receipt", {}).get("resMessage")
        )
        if result == "SUCCESS":
            status = "CONFIRMED_SUCCESS"
        elif result:
            status = f"CONFIRMED_{result}"
        else:
            status = "CONFIRMED"
    elif meta and meta.get("txID"):
        status = "PENDING_OR_UNCONFIRMED"

    return {
        "txid": txid,
        "status": status,
        "blockNumber": info.get("blockNumber") if info else None,
        "blockTime": info.get("blockTimeStamp") if info else None,
        "feeSun": info.get("fee") if info else None,
        "energyUsage": info.get("receipt", {}).get("energy_usage_total") if info else None,
        "rawMeta": meta,
        "rawReceipt": info,
    }


def _direction(address: str, owner: str, to: str) -> str:
    if owner == address and to == address:
        return "SELF"
    if owner == address:
        return "OUT"
    if to == address:
        return "IN"
    return "OTHER"


def get_recent_transactions(address: str, limit: int = 20) -> Dict[str, Any]:
    """Recent tx list (concise)."""
    validate_address(address)
    limit = max(1, min(int(limit or 20), 50))
    data = {}
    source = None
    errors: list[str] = []
    # primary: Trongrid
    try:
        data = fetch_transactions(address, limit=limit, start=0)
        source = "TRONGRID"
    except UpstreamError as err:
        errors.append(f"Trongrid error: {err}")
        # fallback: Tronscan
        try:
            data = fetch_transactions_tronscan(address, limit=limit, start=0)
            source = "TRONSCAN"
        except UpstreamError as err2:
            errors.append(f"Tronscan error: {err2}")
            return {
                "address": address,
                "count": 0,
                "items": [],
                "source": "NONE",
                "error": "; ".join(errors),
            }
    items = []
    for tx in data.get("data", []):
        owner = tx.get("ownerAddress") or tx.get("from")
        to = tx.get("toAddress") or tx.get("to")
        txid = tx.get("txID") or tx.get("hash")
        ts = tx.get("block_timestamp") or tx.get("timestamp") or tx.get("time")
        contract_type = (tx.get("raw_data", {}).get("contract") or [{}])[0].get("type") if tx.get("raw_data") else tx.get("contractType")
        items.append(
            {
                "txid": txid,
                "timestamp": ts,
                "ret": tx.get("ret"),
                "contractType": contract_type,
                "direction": _direction(address, owner, to),
                "from": owner,
                "to": to,
            }
        )
    return {"address": address, "count": len(items), "items": items, "source": source}


def get_trc20_transfers(address: str, limit: int = 20) -> Dict[str, Any]:
    """Recent TRC20 transfers for an address."""
    validate_address(address)
    limit = max(1, min(int(limit or 20), 50))
    data = {}
    source = None
    transfers = []
    errors: list[str] = []
    # primary: Trongrid
    try:
        data = fetch_trc20_transfers(address, limit=limit, start=0)
        source = "TRONGRID"
        transfers = data.get("data") or []
    except UpstreamError as err:
        errors.append(f"Trongrid error: {err}")
        # fallback: Tronscan
        try:
            data = fetch_trc20_transfers_tronscan(address, limit=limit, start=0)
            source = "TRONSCAN"
            transfers = data.get("token_transfers") or data.get("data") or []
        except UpstreamError as err2:
            errors.append(f"Tronscan error: {err2}")
            return {
                "address": address,
                "count": 0,
                "items": [],
                "source": "NONE",
                "error": "; ".join(errors),
            }

    items = []
    for tx in transfers:
        owner = tx.get("from") or tx.get("from_address")
        to = tx.get("to") or tx.get("to_address")
        token_info = tx.get("token_info") or tx.get("tokenInfo") or {}
        amount = tx.get("value") or tx.get("quant") or tx.get("amount")
        decimals = token_info.get("tokenDecimal") or token_info.get("decimals") or 6
        items.append(
            {
                "txid": tx.get("transaction_id") or tx.get("transactionHash"),
                "timestamp": tx.get("block_timestamp") or tx.get("block_ts") or tx.get("timestamp"),
                "token": {
                    "symbol": token_info.get("symbol") or token_info.get("tokenAbbr") or tx.get("tokenName"),
                    "contract": token_info.get("address") or tx.get("contract_address"),
                    "decimals": decimals,
                },
                "amountRaw": str(amount) if amount is not None else None,
                "amountHuman": format_token_amount(str(amount or 0), int(decimals)),
                "from": owner,
                "to": to,
                "direction": _direction(address, owner, to),
            }
        )
    return {"address": address, "count": len(items), "items": items, "source": source}


def get_address_labels(address: str) -> Dict[str, Any]:
    """Return label/name/flags for an address using account payload."""
    validate_address(address)
    acc = fetch_account(address)
    return {
        "address": address,
        "name": acc.get("name") or acc.get("addressTag") or acc.get("ownerAddress"),
        "tags": acc.get("addressTagMap") or acc.get("tags") or acc.get("labels"),
        "isContract": bool(acc.get("isContract")),
        "isShielded": bool(acc.get("isShielded")),
        "source": "TRONSCAN",
        "raw": acc,
    }


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    """Dispatch a tool call by name with argument dict."""
    args = args or {}
    if name == "get_usdt_balance":
        return get_usdt_balance(address=args.get("address"))
    if name == "get_network_params":
        return get_network_params()
    if name == "get_tx_status":
        return get_tx_status(txid=args.get("txid"))
    if name == "get_recent_transactions":
        return get_recent_transactions(address=args.get("address"), limit=args.get("limit", 20))
    if name == "get_trc20_transfers":
        return get_trc20_transfers(address=args.get("address"), limit=args.get("limit", 20))
    if name == "get_address_labels":
        return get_address_labels(address=args.get("address"))
    raise ValidationError(f"Unknown tool name: {name}")
