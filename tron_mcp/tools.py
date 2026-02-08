"""Higher-level tool implementations exposed to MCP."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional
import time
import json
import asyncio
import importlib.util
from pathlib import Path

from . import settings
from .extensions import tx_assistant, trc20_assistant, agent_pipeline, local_signer
from .modules import chain_ops, funds_flow, notify_telegram, bash_tool
from .custom_tools import manager as custom_tools_manager
from .modules import audit_log, market_data, exchange_adapter, risk_monitor, onchain_monitor
from . import custom_tools
from .utils.errors import ValidationError
from .tron_api import (
    fetch_account,
    fetch_account_trongrid,
    fetch_chain_parameters,
    fetch_tx_info,
    fetch_tx_meta,
    fetch_transactions,
    fetch_trc20_transfers,
    fetch_transactions_tronscan,
    fetch_trc20_transfers_tronscan,
    fetch_tron_token_prices,
    fetch_trx_price,
)
from .utils import format_token_amount, validate_address, validate_txid
from .utils.encoding import tron_hex_to_b58
from .utils import ADDRESS_RE, format_token_amount, validate_address, validate_txid
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
        name="get_trx_balance",
        description="Fetch TRX balance for an address (TRONGRID).",
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
    Tool(
        name="get_token_balance",
        description="Fetch balance for any token (TRX or TRC20 by symbol/contract) using TRONSCAN.",
        inputSchema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "TRON Base58 address starting with T"},
                "token": {
                    "type": "string",
                    "description": "Token symbol (e.g. USDT/TRX) or TRC20 contract address",
                },
            },
            "required": ["address", "token"],
        },
    ),
    Tool(
        name="get_total_value",
        description="Calculate total portfolio value for all tokens (TRX + TRC20) in USD/CNY.",
        inputSchema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "TRON Base58 address starting with T"},
                "currency": {
                    "type": "string",
                    "description": "Fiat unit: usd or cny",
                    "enum": ["usd", "cny"],
                },
            },
            "required": ["address"],
        },
    ),
    Tool(
        name="get_transactions_between_addresses",
        description="List transactions between two addresses within a time range (TRONGRID → TRONSCAN).",
        inputSchema={
            "type": "object",
            "properties": {
                "address_a": {"type": "string", "description": "TRON Base58 address"},
                "address_b": {"type": "string", "description": "TRON Base58 address"},
                "start_ts_ms": {"type": "integer", "description": "Start time (Unix ms)"},
                "end_ts_ms": {"type": "integer", "description": "End time (Unix ms, default now)"},
                "limit": {"type": "integer", "description": "Page size, 1-50", "minimum": 1, "maximum": 50},
                "max_pages": {"type": "integer", "description": "Max pages to scan", "minimum": 1, "maximum": 200},
            },
            "required": ["address_a", "address_b", "start_ts_ms"],
        },
    ),
    Tool(
        name="get_wallet_balance",
        description="Get TRON wallet portfolio summary (TRX + TRC20) with USD valuation.",
        inputSchema={
            "type": "object",
            "properties": {"address": {"type": "string", "description": "TRON Base58 address starting with T"}},
            "required": ["address"],
        },
    ),
    Tool(
        name="get_token_price",
        description="Get token price in USD by symbol or TRC20 contract address.",
        inputSchema={
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Token symbol (TRX/USDT) or TRC20 contract address"}
            },
            "required": ["symbol"],
        },
    ),
    Tool(
        name="get_token_security",
        description="Lightweight token contract security check (simulated).",
        inputSchema={
            "type": "object",
            "properties": {
                "token_address": {"type": "string", "description": "TRON contract address starting with T"}
            },
            "required": ["token_address"],
        },
    ),
    Tool(
        name="simulate_transaction",
        description="Simulate a transaction by raw hex (lightweight, simulated).",
        inputSchema={
            "type": "object",
            "properties": {"transaction_hex": {"type": "string", "description": "Raw transaction hex"}},
            "required": ["transaction_hex"],
        },
    ),
    Tool(
        name="swap_tokens",
        description="Build an unsigned swap transaction on SunSwap V2.",
        inputSchema={
            "type": "object",
            "properties": {
                "address": {"type": "string", "description": "Sender wallet address"},
                "token_in": {"type": "string", "description": "Input token symbol or address, or TRX"},
                "token_out": {"type": "string", "description": "Output token symbol or address, or TRX"},
                "amount_in": {"type": "number", "description": "Amount of input token"},
                "slippage": {"type": "number", "description": "Slippage tolerance, percent"},
            },
            "required": ["address", "token_in", "token_out", "amount_in"],
        },
    ),
    Tool(
        name="rent_energy",
        description="Estimate energy rental cost and recommendations.",
        inputSchema={
            "type": "object",
            "properties": {
                "amount": {"type": "integer", "description": "Energy amount to rent"},
                "duration_days": {"type": "integer", "description": "Rental duration in days"},
            },
            "required": ["amount"],
        },
    ),
    Tool(
        name="check_address_security",
        description="Check security risk level of a TRON address.",
        inputSchema={
            "type": "object",
            "properties": {"address": {"type": "string", "description": "TRON address"}},
            "required": ["address"],
        },
    ),
    Tool(
        name="record_transfer",
        description="Record transfer in address book (lookup or save recipient).",
        inputSchema={
            "type": "object",
            "properties": {"to_address": {"type": "string", "description": "Recipient TRON address"}},
            "required": ["to_address"],
        },
    ),
    Tool(
        name="check_malicious",
        description="Check if address is malicious on TronScan blacklist.",
        inputSchema={
            "type": "object",
            "properties": {"address": {"type": "string", "description": "TRON address"}},
            "required": ["address"],
        },
    ),
    Tool(
        name="calculate_energy",
        description="Estimate energy usage for TRC20 transfers.",
        inputSchema={
            "type": "object",
            "properties": {"token": {"type": "string", "description": "Token symbol (e.g., USDT)"}},
            "required": ["token"],
        },
    ),
    Tool(
        name="build_transfer",
        description="Build unsigned transfer transaction (TRX or TRC20).",
        inputSchema={
            "type": "object",
            "properties": {
                "from_address": {"type": "string", "description": "Sender TRON address"},
                "to_address": {"type": "string", "description": "Recipient TRON address"},
                "token": {"type": "string", "description": "Token symbol or contract"},
                "amount": {"type": "number", "description": "Amount to transfer"},
                "memo": {"type": "string", "description": "Optional memo"},
            },
            "required": ["from_address", "to_address", "token", "amount"],
        },
    ),
    Tool(
        name="transfer_tokens",
        description="Quick transfer (combines steps and builds unsigned tx).",
        inputSchema={
            "type": "object",
            "properties": {
                "from_address": {"type": "string", "description": "Sender TRON address"},
                "to_address": {"type": "string", "description": "Recipient TRON address"},
                "token": {"type": "string", "description": "Token symbol or contract"},
                "amount": {"type": "number", "description": "Amount to transfer"},
                "memo": {"type": "string", "description": "Optional memo"},
            },
            "required": ["from_address", "to_address", "token", "amount"],
        },
    ),
    Tool(
        name="analyze_error",
        description="Analyze blockchain/transaction errors.",
        inputSchema={
            "type": "object",
            "properties": {"error_message": {"type": "string", "description": "Error message"}},
            "required": ["error_message"],
        },
    ),
    Tool(
        name="manage_skill",
        description="Save or delete a generated skill.",
        inputSchema={
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "Skill name"},
                "action": {"type": "string", "enum": ["save", "delete"]},
            },
            "required": ["skill_name", "action"],
        },
    ),
]

_SKILL_CACHE: Dict[str, Any] = {}


def _run_async(coro: Any) -> Any:
    if not asyncio.iscoroutine(coro):
        return coro
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


def _load_skill_function(relative_path: str, func_name: str) -> Any:
    key = f"{relative_path}:{func_name}"
    if key in _SKILL_CACHE:
        return _SKILL_CACHE[key]
    project_root = Path(__file__).resolve().parents[1]
    module_path = project_root / relative_path
    spec = importlib.util.spec_from_file_location(f"compat_{func_name}", module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    func = getattr(module, func_name)
    _SKILL_CACHE[key] = func
    return func


def _load_wrapper_function(func_name: str) -> Any:
    return _load_skill_function("src/tool_wrappers.py", func_name)


def _load_personal_skills_tool_defs() -> List[Dict[str, Any]]:
    tools: List[Dict[str, Any]] = []
    skills_dir = Path(__file__).resolve().parents[1] / "personal-skills"
    if not skills_dir.exists():
        return tools
    for skill_dir in skills_dir.iterdir():
        if not skill_dir.is_dir():
            continue
        tool_json = skill_dir / "skill.json"
        if tool_json.exists():
            try:
                tools.append(json.loads(tool_json.read_text(encoding="utf-8")))
            except Exception:
                continue
    return tools


def list_tools() -> Dict[str, Any]:
    """Return tool definitions for MCP list_tools."""
    tools = [t.to_dict() for t in TOOL_DEFINITIONS]
    tools.extend(tx_assistant.TOOL_DEFINITIONS)
    tools.extend(trc20_assistant.TOOL_DEFINITIONS)
    tools.extend(agent_pipeline.TOOL_DEFINITIONS)
    tools.extend(local_signer.TOOL_DEFINITIONS)
    tools.extend(custom_tools.get_tool_definitions())
    tools.extend(custom_tools_manager.TOOL_DEFINITIONS)
    tools.extend(chain_ops.TOOL_DEFINITIONS)
    tools.extend(funds_flow.TOOL_DEFINITIONS)
    tools.extend(notify_telegram.TOOL_DEFINITIONS)
    tools.extend(bash_tool.TOOL_DEFINITIONS)
    tools.extend(audit_log.TOOL_DEFINITIONS)
    tools.extend(market_data.TOOL_DEFINITIONS)
    tools.extend(exchange_adapter.TOOL_DEFINITIONS)
    tools.extend(risk_monitor.TOOL_DEFINITIONS)
    tools.extend(onchain_monitor.TOOL_DEFINITIONS)
    tools.extend(_load_personal_skills_tool_defs())
    return {"tools": tools}


def _token_contract(token: Dict[str, Any]) -> Optional[str]:
    return (
        token.get("tokenId")
        or token.get("contract_address")
        or token.get("tokenAddress")
        or token.get("token_id")
        or token.get("tokenIdAddress")
        or token.get("address")
    )


def _token_symbol(token: Dict[str, Any]) -> Optional[str]:
    return (
        token.get("tokenAbbr")
        or token.get("symbol")
        or token.get("tokenSymbol")
        or token.get("tokenName")
        or token.get("name")
    )


def _token_decimals(token: Dict[str, Any], default: int = 6) -> int:
    return int(token.get("tokenDecimal") or token.get("decimals") or token.get("tokenDecimals") or default)


def _token_balance_raw(token: Dict[str, Any]) -> str:
    for key in ("balance", "amount", "tokenBalance", "quantity"):
        candidate = token.get(key)
        if candidate not in (None, "", "0"):
            return str(candidate)
    return "0"


def _get_trc20_candidates(account: Dict[str, Any]) -> List[Dict[str, Any]]:
    return (
        account.get("trc20token_balances")
        or account.get("trc20token_balancesV2")
        or account.get("trc20")
        or account.get("tokenBalances")
        or []
    )


def _tx_timestamp_ms(tx: Dict[str, Any]) -> Optional[int]:
    ts = (
        tx.get("block_timestamp")
        or tx.get("timestamp")
        or tx.get("time")
        or tx.get("block_ts")
        or tx.get("blockTimeStamp")
    )
    try:
        return int(ts) if ts is not None else None
    except (TypeError, ValueError):
        return None


def _tx_owner_to(tx: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    owner = _normalize_address(tx.get("ownerAddress") or tx.get("from"))
    to = _normalize_address(tx.get("toAddress") or tx.get("to"))
    if not owner or not to:
        raw_owner, raw_to = _extract_owner_to_from_raw(tx)
        owner = owner or _normalize_address(raw_owner)
        to = to or _normalize_address(raw_to)
    return owner, to


def _match_between(owner: Optional[str], to: Optional[str], a: str, b: str) -> Optional[str]:
    if owner == a and to == b:
        return "A_TO_B"
    if owner == b and to == a:
        return "B_TO_A"
    return None


def get_transactions_between_addresses(
    address_a: str,
    address_b: str,
    start_ts_ms: int,
    end_ts_ms: Optional[int] = None,
    limit: int = 50,
    max_pages: int = 10,
) -> Dict[str, Any]:
    validate_address(address_a)
    validate_address(address_b)
    start_ts = int(start_ts_ms)
    end_ts = int(end_ts_ms) if end_ts_ms is not None else int(time.time() * 1000)
    if start_ts > end_ts:
        raise ValidationError("start_ts_ms must be <= end_ts_ms")
    limit = max(1, min(int(limit or 50), 50))
    max_pages = max(1, min(int(max_pages or 10), 200))

    items: List[Dict[str, Any]] = []
    errors: list[str] = []
    source = None

    # Try TRONGRID first
    try:
        fp: Any = 0
        for _ in range(max_pages):
            data = fetch_transactions(address_a, limit=limit, start=fp or 0)
            source = "TRONGRID"
            rows = data.get("data") or []
            if not rows:
                break
            stop = False
            for tx in rows:
                ts = _tx_timestamp_ms(tx)
                if ts is not None and ts < start_ts:
                    stop = True
                    break
                if ts is not None and ts > end_ts:
                    continue
                owner, to = _tx_owner_to(tx)
                direction = _match_between(owner, to, address_a, address_b)
                if not direction:
                    continue
                items.append(
                    {
                        "txid": tx.get("txID") or tx.get("hash"),
                        "timestamp": ts,
                        "from": owner,
                        "to": to,
                        "direction": direction,
                        "contractType": (tx.get("raw_data", {}).get("contract") or [{}])[0].get("type")
                        if tx.get("raw_data")
                        else tx.get("contractType"),
                    }
                )
            if stop:
                break
            fp = (data.get("meta") or {}).get("fingerprint")
            if not fp:
                break
        return {
            "addressA": address_a,
            "addressB": address_b,
            "startTsMs": start_ts,
            "endTsMs": end_ts,
            "count": len(items),
            "items": items,
            "source": source or "TRONGRID",
        }
    except UpstreamError as err:
        errors.append(f"Trongrid error: {err}")

    # Fallback: TRONSCAN
    try:
        start = 0
        for _ in range(max_pages):
            data = fetch_transactions_tronscan(address_a, limit=limit, start=start)
            source = "TRONSCAN"
            rows = data.get("data") or data.get("transactions") or []
            if not rows:
                break
            stop = False
            for tx in rows:
                ts = _tx_timestamp_ms(tx)
                if ts is not None and ts < start_ts:
                    stop = True
                    break
                if ts is not None and ts > end_ts:
                    continue
                owner, to = _tx_owner_to(tx)
                direction = _match_between(owner, to, address_a, address_b)
                if not direction:
                    continue
                items.append(
                    {
                        "txid": tx.get("txID") or tx.get("hash"),
                        "timestamp": ts,
                        "from": owner,
                        "to": to,
                        "direction": direction,
                        "contractType": (tx.get("raw_data", {}).get("contract") or [{}])[0].get("type")
                        if tx.get("raw_data")
                        else tx.get("contractType"),
                    }
                )
            if stop:
                break
            if len(rows) < limit:
                break
            start += limit
        return {
            "addressA": address_a,
            "addressB": address_b,
            "startTsMs": start_ts,
            "endTsMs": end_ts,
            "count": len(items),
            "items": items,
            "source": source or "TRONSCAN",
        }
    except UpstreamError as err:
        errors.append(f"Tronscan error: {err}")
        return {
            "addressA": address_a,
            "addressB": address_b,
            "startTsMs": start_ts,
            "endTsMs": end_ts,
            "count": 0,
            "items": [],
            "source": "NONE",
            "error": "; ".join(errors),
        }


def _parse_decimal(value: str) -> Optional[Decimal]:
    try:
        return Decimal(value)
    except (InvalidOperation, TypeError):
        return None


def _clean_contracts(contracts: list[Optional[str]]) -> list[str]:
    cleaned = []
    seen = set()
    for contract in contracts:
        if not contract:
            continue
        value = str(contract).strip()
        if not value or "," in value or " " in value:
            continue
        if not ADDRESS_RE.fullmatch(value):
            continue
        if value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def get_usdt_balance(address: str) -> Dict[str, Any]:
    """Lookup TRC20 USDT balance via TRONSCAN payload fields."""
    validate_address(address)
    account = fetch_account(address)

    candidates = _get_trc20_candidates(account)

    usdt = None
    for token in candidates:
        contract = _token_contract(token)
        if contract and contract.upper() == settings.SETTINGS.usdt_contract.upper():
            usdt = token
            break

    balance_raw = _token_balance_raw(usdt) if usdt else "0"
    decimals = _token_decimals(usdt) if usdt else 6

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


def get_trx_balance(address: str) -> Dict[str, Any]:
    """Lookup TRX balance via TRONGRID account payload."""
    validate_address(address)
    account = fetch_account_trongrid(address)
    balance_sun = int(account.get("balance") or 0)
    return {
        "address": address,
        "balance": {
            "raw": str(balance_sun),
            "human": format_token_amount(str(balance_sun), 6),
            "decimals": 6,
        },
        "source": "TRONGRID",
        "apiUrl": f"{settings.SETTINGS.trongrid_base}/wallet/getaccount",
        "updated": None,
        "raw": account,
    }
def get_token_balance(address: str, token: str) -> Dict[str, Any]:
    """Lookup TRX/TRC20 token balance by symbol or contract (TRONSCAN)."""
    validate_address(address)
    if not token:
        raise ValidationError("token is required")

    token_key = token.strip()
    token_upper = token_key.upper()

    account = fetch_account(address)
    api_url = f"{settings.SETTINGS.tronscan_base}/account?address={address}"

    if token_upper in {"TRX", "TRON"}:
        balance_raw = str(account.get("balance") or account.get("balanceInSun") or 0)
        decimals = 6
        return {
            "address": address,
            "token": {
                "symbol": "TRX",
                "contract": None,
                "decimals": decimals,
                "name": "TRON",
                "matchedBy": "native",
            },
            "balance": {
                "raw": balance_raw,
                "human": format_token_amount(balance_raw, decimals),
                "decimals": decimals,
            },
            "source": "TRONSCAN",
            "apiUrl": api_url,
            "updated": account.get("updateTime") or account.get("date_updated"),
        }

    candidates = _get_trc20_candidates(account)
    matched = None
    matched_by = None
    for token_item in candidates:
        contract = _token_contract(token_item)
        symbol = _token_symbol(token_item)
        if contract and contract.upper() == token_upper:
            matched = token_item
            matched_by = "contract"
            break
        if symbol and symbol.upper() == token_upper:
            matched = token_item
            matched_by = "symbol"
            break

    if not matched:
        raise ValidationError(f"Token not found for address: {token_key}")

    contract = _token_contract(matched)
    symbol = _token_symbol(matched)
    decimals = _token_decimals(matched)
    balance_raw = _token_balance_raw(matched)
    return {
        "address": address,
        "token": {
            "symbol": symbol or token_upper,
            "contract": contract,
            "decimals": decimals,
            "name": matched.get("tokenName") or matched.get("name"),
            "matchedBy": matched_by,
        },
        "balance": {
            "raw": balance_raw,
            "human": format_token_amount(balance_raw, decimals),
            "decimals": decimals,
        },
        "source": "TRONSCAN",
        "apiUrl": api_url,
        "updated": account.get("updateTime") or account.get("date_updated"),
    }


def get_total_value(address: str, currency: str = "usd") -> Dict[str, Any]:
    """Calculate total value for TRX + TRC20 tokens in usd/cny."""
    validate_address(address)
    currency = (currency or "usd").lower()
    if currency not in {"usd", "cny"}:
        raise ValidationError("currency must be 'usd' or 'cny'")

    account = fetch_account(address)
    api_url = f"{settings.SETTINGS.tronscan_base}/account?address={address}"

    items: list[Dict[str, Any]] = []

    trx_raw = str(account.get("balance") or account.get("balanceInSun") or 0)
    trx_decimals = 6
    trx_human = format_token_amount(trx_raw, trx_decimals)
    items.append(
        {
            "token": {"symbol": "TRX", "contract": None, "decimals": trx_decimals, "name": "TRON"},
            "balance": {"raw": trx_raw, "human": trx_human, "decimals": trx_decimals},
        }
    )

    candidates = _get_trc20_candidates(account)
    for token_item in candidates:
        contract = _token_contract(token_item)
        symbol = _token_symbol(token_item)
        decimals = _token_decimals(token_item)
        balance_raw = _token_balance_raw(token_item)
        items.append(
            {
                "token": {
                    "symbol": symbol,
                    "contract": contract,
                    "decimals": decimals,
                    "name": token_item.get("tokenName") or token_item.get("name"),
                },
                "balance": {
                    "raw": balance_raw,
                    "human": format_token_amount(balance_raw, decimals),
                    "decimals": decimals,
                },
            }
        )

    contracts = _clean_contracts([item["token"]["contract"] for item in items if item["token"]["contract"]])
    price_map: dict[str, dict[str, Any]] = {}
    pricing_errors: list[str] = []
    if contracts:
        chunk_size = 80
        for idx in range(0, len(contracts), chunk_size):
            chunk = contracts[idx : idx + chunk_size]
            try:
                chunk_prices = fetch_tron_token_prices(chunk, currency) or {}
                for key, val in chunk_prices.items():
                    price_map[str(key).lower()] = val
            except UpstreamError as err:
                pricing_errors.append(f"CoinGecko chunk {idx // chunk_size + 1}: {err}")
    try:
        trx_price_raw = fetch_trx_price(currency)
    except UpstreamError as err:
        trx_price_raw = {}
        pricing_errors.append(f"CoinGecko TRX price: {err}")
    trx_price = (trx_price_raw.get("tron") or {}).get(currency)

    total_value = Decimal("0")
    missing_prices: list[str] = []

    for item in items:
        contract = item["token"]["contract"]
        symbol = item["token"]["symbol"] or contract or "UNKNOWN"
        price = trx_price if not contract else (price_map.get(str(contract).lower()) or {}).get(currency)
        value = None

        amount = _parse_decimal(item["balance"]["human"])
        price_dec = _parse_decimal(str(price)) if price is not None else None
        if amount is not None and price_dec is not None:
            value = amount * price_dec
            total_value += value
            item["price"] = float(price_dec)
            item["value"] = str(value)
        else:
            item["price"] = float(price) if price is not None else None
            item["value"] = None
            missing_prices.append(str(symbol))

    return {
        "address": address,
        "currency": currency,
        "totalValue": str(total_value),
        "items": items,
        "missingPrices": missing_prices,
        "pricingErrors": pricing_errors,
        "pricingSource": "COINGECKO",
        "apiUrl": {
            "account": api_url,
            "prices": settings.SETTINGS.coingecko_base,
        },
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

    owner = None
    to = None
    amount = None
    if meta:
        raw_owner, raw_to = _extract_owner_to_from_raw(meta)
        owner = _normalize_address(raw_owner)
        to = _normalize_address(raw_to)
        raw = meta.get("raw_data") or {}
        contract = (raw.get("contract") or [{}])[0] or {}
        value = (contract.get("parameter") or {}).get("value") or {}
        amount = value.get("amount")

    return {
        "txid": txid,
        "status": status,
        "blockNumber": info.get("blockNumber") if info else None,
        "blockTime": info.get("blockTimeStamp") if info else None,
        "feeSun": info.get("fee") if info else None,
        "energyUsage": info.get("receipt", {}).get("energy_usage_total") if info else None,
        "from": owner,
        "to": to,
        "amountSun": amount,
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


def _normalize_address(value: str | None) -> str | None:
    if not value:
        return None
    if isinstance(value, str):
        v = value.lower().replace("0x", "")
        if len(v) == 42 and all(ch in "0123456789abcdef" for ch in v):
            try:
                return tron_hex_to_b58(v)
            except Exception:
                return value
    return value


def _extract_owner_to_from_raw(tx: Dict[str, Any]) -> tuple[str | None, str | None]:
    raw = tx.get("raw_data") or {}
    contract = (raw.get("contract") or [{}])[0] or {}
    value = (contract.get("parameter") or {}).get("value") or {}
    owner = value.get("owner_address") or value.get("ownerAddress")
    to = value.get("to_address") or value.get("toAddress")
    return owner, to


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
        owner = _normalize_address(tx.get("ownerAddress") or tx.get("from"))
        to = _normalize_address(tx.get("toAddress") or tx.get("to"))
        if not owner or not to:
            raw_owner, raw_to = _extract_owner_to_from_raw(tx)
            owner = owner or _normalize_address(raw_owner)
            to = to or _normalize_address(raw_to)
        txid = tx.get("txID") or tx.get("hash")
        ts = tx.get("block_timestamp") or tx.get("timestamp") or tx.get("time")
        contract_type = (tx.get("raw_data", {}).get("contract") or [{}])[0].get("type") if tx.get("raw_data") else tx.get("contractType")
        items.append(
            {
                "txid": txid,
                "timestamp": ts,
                "ret": tx.get("ret"),
                "contractType": contract_type,
                "direction": _direction(address, owner or "", to or ""),
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
        owner = _normalize_address(tx.get("from") or tx.get("from_address"))
        to = _normalize_address(tx.get("to") or tx.get("to_address"))
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
                "direction": _direction(address, owner or "", to or ""),
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


def get_wallet_balance(address: str) -> Dict[str, Any]:
    """Portfolio summary using existing TRONSCAN + CoinGecko pipeline."""
    data = get_total_value(address, currency="usd")
    if not isinstance(data, dict):
        return {"address": address, "error": "Unexpected response"}
    return {
        "address": address,
        "currency": data.get("currency", "usd"),
        "totalValue": data.get("totalValue"),
        "items": data.get("items", []),
        "missingPrices": data.get("missingPrices", []),
        "pricingSource": data.get("pricingSource"),
        "source": data.get("source", "TRONSCAN"),
    }


def get_token_price(symbol: str) -> Dict[str, Any]:
    """Token price in USD by symbol or contract address."""
    symbol = (symbol or "").strip()
    if not symbol:
        return {"error": "symbol is required"}
    symbol_upper = symbol.upper()

    if symbol_upper == "TRX":
        data = fetch_trx_price("usd")
        price = data.get("tron", {}).get("usd")
        return {"symbol": "TRX", "usd_price": price, "source": "CoinGecko", "raw": data}

    if symbol_upper == "USDT":
        return {"symbol": "USDT", "usd_price": 1.0, "source": "stablecoin"}

    if symbol.startswith("T") and len(symbol) == 34:
        data = fetch_tron_token_prices([symbol], "usd")
        key = symbol.lower()
        price = data.get(key, {}).get("usd") if isinstance(data, dict) else None
        return {"symbol": symbol, "usd_price": price, "source": "CoinGecko", "raw": data}

    return {"symbol": symbol, "usd_price": None, "error": "Unknown symbol; provide contract address."}


def get_token_security(token_address: str) -> Dict[str, Any]:
    """Simple token contract security hints (simulated)."""
    known_safe = {
        "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # USDT
        "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9",  # BTTC
        "TSSMHYeV2uE9qYH95DqyoCuNCzEL1NvU3S",  # SUN
    }
    status = "SAFE" if token_address in known_safe else "UNKNOWN"
    return {
        "token_address": token_address,
        "status": status,
        "notes": "Simulated check; verify contract and audits before trading.",
    }


def simulate_transaction(transaction_hex: str) -> Dict[str, Any]:
    """Simulated transaction check (placeholder)."""
    if not transaction_hex:
        return {"error": "transaction_hex is required"}
    return {
        "status": "SUCCESS",
        "energy_estimate": 15000,
        "bandwidth_estimate": 300,
        "risk_check": "PASS",
        "note": "Simulation only. Real execution depends on chain state.",
    }


def swap_tokens(
    address: str,
    token_in: str,
    token_out: str,
    amount_in: float,
    slippage: float = 0.5,
) -> Dict[str, Any]:
    """Build unsigned SunSwap V2 swap transaction."""
    build_swap_transaction = _load_skill_function(
        "skills/swap-tokens/scripts/build_swap.py",
        "build_swap_transaction",
    )
    return _run_async(build_swap_transaction(address, token_in, token_out, amount_in, slippage))


def rent_energy(amount: int, duration_days: int = 3) -> Dict[str, Any]:
    """Energy rental proposal (uses skill logic)."""
    get_rental_proposal = _load_skill_function(
        "skills/energy-rental/scripts/calculate_rental.py",
        "get_rental_proposal",
    )
    return _run_async(get_rental_proposal(amount, duration_days))


def check_address_security(address: str) -> Any:
    tool_fn = _load_wrapper_function("tool_check_address_security")
    return _run_async(tool_fn(address))


def record_transfer(to_address: str) -> str:
    get_contact_alias = _load_skill_function(
        "skills/address-book/scripts/manage_contacts.py",
        "get_contact_alias",
    )
    save_contact = _load_skill_function(
        "skills/address-book/scripts/manage_contacts.py",
        "save_contact",
    )
    alias = get_contact_alias(to_address)
    contact_info = save_contact(to_address, alias=alias, increment_count=True)
    transfer_count = contact_info.get("transfer_count", 1)
    if alias:
        return (
            "📇 **地址簿记录**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"✅ 找到已保存联系人: **{alias}**\n"
            f"📊 历史转账次数: **第 {transfer_count} 次**\n\n"
            "→ 已知地址，安全性较高"
        )
    return (
        "📇 **地址簿记录**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "ℹ️ 新地址，首次转账\n"
        "📊 已添加到地址簿\n\n"
        f"💡 提示: 使用 `/save-contact {to_address[:8]}... <名称>` 可以添加别名"
    )


def check_malicious(address: str, network: str = "nile") -> str:
    check_malicious_address = _load_skill_function(
        "skills/malicious-address-detector/scripts/check_malicious.py",
        "check_malicious_address",
    )
    result = _run_async(check_malicious_address(address, network))
    if result.get("is_malicious"):
        return (
            "🚨 **恶意地址检测**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "❌ **危险: 此地址已被标记为恶意地址!**\n\n"
            f"⚠️ 标签: {', '.join(result.get('tags', ['Scam']))}\n"
            f"⚠️ 警告: {result.get('warnings', ['请勿向此地址转账'])[0]}\n\n"
            "🛑 **强烈建议取消此次转账!**"
        )
    if result.get("risk_level") == "WARNING":
        return (
            "🚨 **恶意地址检测**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ 需要注意: {result.get('warnings', [''])[0]}\n\n"
            "→ 建议谨慎操作"
        )
    return (
        "🚨 **恶意地址检测**\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "✅ 未发现恶意标签\n"
        "📊 数据来源: TronScan\n\n"
        "→ 可以继续下一步"
    )


def calculate_energy(token: str, network: str = "nile") -> str:
    if token.upper() == "TRX":
        return (
            "⚡ **能量计算**\n"
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            "ℹ️ TRX 转账不需要能量，只需带宽\n"
            "📊 预计消耗: ~270 带宽\n\n"
            "→ 无需租赁能量，可以直接转账"
        )
    get_rental_proposal = _load_skill_function(
        "skills/energy-rental/scripts/calculate_rental.py",
        "get_rental_proposal",
    )
    result = _run_async(get_rental_proposal(28000, 1, True))
    if isinstance(result, dict) and result.get("error"):
        return f"⚠️ 能量计算失败: {result['error']}"
    burn_cost = result.get("burn_cost_trx", 0) if isinstance(result, dict) else 0
    rec = result.get("recommendation", {}) if isinstance(result, dict) else {}
    action = rec.get("action", "unknown")
    output = (
        f"⚡ **能量计算** ({token.upper()})\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "📊 预计消耗: ~28,000 能量\n\n"
        "💰 成本对比:\n"
        f"  燃烧 TRX: {burn_cost:.2f} TRX"
    )
    if isinstance(result, dict) and result.get("rental_options"):
        best = result["rental_options"][0]
        output += (
            f"\n  租赁能量: {best['cost_trx']:.2f} TRX (节省 {best['savings_percent']:.0f}%)\n\n"
            f"💡 建议: **{action.upper()}**"
        )
    return output


def build_transfer(
    from_address: str,
    to_address: str,
    token: str,
    amount: float,
    memo: str = "",
    network: str = "nile",
) -> Any:
    if not from_address:
        return "❌ Error: from_address is required for build_transfer."
    tool_fn = _load_wrapper_function("tool_transfer_tokens")
    return _run_async(tool_fn(from_address, to_address, token, amount, memo, network))


def transfer_tokens(
    from_address: str,
    to_address: str,
    token: str,
    amount: float,
    memo: str = "",
    network: str = "nile",
) -> Any:
    if not from_address:
        return "❌ Error: from_address is required for transfer_tokens."
    tool_fn = _load_wrapper_function("tool_transfer_tokens")
    return _run_async(tool_fn(from_address, to_address, token, amount, memo, network))


def analyze_error(error_message: str) -> Any:
    analyze_fn = _load_skill_function(
        "skills/error-analysis/scripts/analyze_error.py",
        "analyze_error",
    )
    return _run_async(analyze_fn(error_message))


def manage_skill(skill_name: str, action: str) -> str:
    import shutil
    base_dir = Path(__file__).resolve().parents[1] / "personal-skills" / skill_name
    if action == "delete":
        if base_dir.exists():
            shutil.rmtree(base_dir)
            return f"🗑️ 技能 '{skill_name}' 已删除。"
        return f"⚠️ 技能 '{skill_name}' 不存在。"
    if action == "save":
        if base_dir.exists():
            return f"💾 技能 '{skill_name}' 已确认保存到个人技能库。"
        return f"⚠️ 技能 '{skill_name}' 不存在，无法保存。"
    return "⚠️ 未知操作，请使用 save 或 delete。"


def _execute_personal_skill(tool_name: str, tool_args: Dict[str, Any]) -> Any:
    skill_dir = Path(__file__).resolve().parents[1] / "personal-skills" / tool_name / "scripts" / "main.py"
    if not skill_dir.exists():
        raise ValidationError(f"Unknown tool name: {tool_name}")
    spec = importlib.util.spec_from_file_location("personal_skill", skill_dir)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    if not hasattr(module, "execute_skill"):
        raise ValidationError(f"Skill '{tool_name}' has no execute_skill function.")
    return _run_async(module.execute_skill(**tool_args))


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    """Dispatch a tool call by name with argument dict."""
    args = args or {}
    if name == "get_usdt_balance":
        return get_usdt_balance(address=args.get("address"))
    if name == "get_trx_balance":
        return get_trx_balance(address=args.get("address"))
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
    if name == "get_transactions_between_addresses":
        return get_transactions_between_addresses(
            address_a=args.get("address_a"),
            address_b=args.get("address_b"),
            start_ts_ms=args.get("start_ts_ms"),
            end_ts_ms=args.get("end_ts_ms"),
            limit=args.get("limit", 50),
            max_pages=args.get("max_pages", 10),
        )
    if name == "get_wallet_balance":
        return get_wallet_balance(address=args.get("address"))
    if name == "get_token_price":
        return get_token_price(symbol=args.get("symbol"))
    if name == "get_token_security":
        return get_token_security(token_address=args.get("token_address"))
    if name == "simulate_transaction":
        return simulate_transaction(transaction_hex=args.get("transaction_hex"))
    if name == "swap_tokens":
        return swap_tokens(
            address=args.get("address"),
            token_in=args.get("token_in"),
            token_out=args.get("token_out"),
            amount_in=args.get("amount_in"),
            slippage=args.get("slippage", 0.5),
        )
    if name == "rent_energy":
        return rent_energy(amount=args.get("amount"), duration_days=args.get("duration_days", 3))
    if name == "check_address_security":
        return check_address_security(address=args.get("address"))
    if name == "record_transfer":
        return record_transfer(to_address=args.get("to_address"))
    if name == "check_malicious":
        return check_malicious(address=args.get("address"), network=args.get("network", "nile"))
    if name == "calculate_energy":
        return calculate_energy(token=args.get("token", "TRX"), network=args.get("network", "nile"))
    if name == "build_transfer":
        return build_transfer(
            from_address=args.get("from_address"),
            to_address=args.get("to_address"),
            token=args.get("token", "TRX"),
            amount=args.get("amount", 0),
            memo=args.get("memo", ""),
            network=args.get("network", "nile"),
        )
    if name == "transfer_tokens":
        return transfer_tokens(
            from_address=args.get("from_address"),
            to_address=args.get("to_address"),
            token=args.get("token", "TRX"),
            amount=args.get("amount", 0),
            memo=args.get("memo", ""),
            network=args.get("network", "nile"),
        )
    if name == "analyze_error":
        return analyze_error(error_message=args.get("error_message", ""))
    if name == "manage_skill":
        return manage_skill(skill_name=args.get("skill_name", ""), action=args.get("action", ""))
    if name in tx_assistant.TOOL_NAMES:
        return tx_assistant.call_tool(name, args)
    if name in trc20_assistant.TOOL_NAMES:
        return trc20_assistant.call_tool(name, args)
    if name in agent_pipeline.TOOL_NAMES:
        return agent_pipeline.call_tool(name, args)
    if name in local_signer.TOOL_NAMES:
        return local_signer.call_tool(name, args)
    if name in custom_tools.get_tool_names():
        return custom_tools.call_tool(name, args)
    if name in chain_ops.TOOL_NAMES:
        return chain_ops.call_tool(name, args)
    if name in funds_flow.TOOL_NAMES:
        return funds_flow.call_tool(name, args)
    if name in notify_telegram.TOOL_NAMES:
        return notify_telegram.call_tool(name, args)
    if name in bash_tool.TOOL_NAMES:
        return bash_tool.call_tool(name, args)
    if name in audit_log.TOOL_NAMES:
        return audit_log.call_tool(name, args)
    if name in market_data.TOOL_NAMES:
        return market_data.call_tool(name, args)
    if name in exchange_adapter.TOOL_NAMES:
        return exchange_adapter.call_tool(name, args)
    if name in risk_monitor.TOOL_NAMES:
        return risk_monitor.call_tool(name, args)
    if name in onchain_monitor.TOOL_NAMES:
        return onchain_monitor.call_tool(name, args)
    if name == "get_token_balance":
        return get_token_balance(address=args.get("address"), token=args.get("token"))
    if name == "get_total_value":
        return get_total_value(address=args.get("address"), currency=args.get("currency", "usd"))
    return _execute_personal_skill(name, args)
