"""Higher-level tool implementations exposed to MCP."""

from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional

from . import settings
from .extensions import tx_assistant, trc20_assistant, agent_pipeline, local_signer
from .modules import chain_ops, funds_flow, notify_telegram, bash_tool
from .modules import audit_log, market_data, exchange_adapter, risk_monitor, onchain_monitor
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
]


def list_tools() -> Dict[str, Any]:
    """Return tool definitions for MCP list_tools."""
    tools = [t.to_dict() for t in TOOL_DEFINITIONS]
    tools.extend(tx_assistant.TOOL_DEFINITIONS)
    tools.extend(trc20_assistant.TOOL_DEFINITIONS)
    tools.extend(agent_pipeline.TOOL_DEFINITIONS)
    tools.extend(local_signer.TOOL_DEFINITIONS)
    tools.extend(chain_ops.TOOL_DEFINITIONS)
    tools.extend(funds_flow.TOOL_DEFINITIONS)
    tools.extend(notify_telegram.TOOL_DEFINITIONS)
    tools.extend(bash_tool.TOOL_DEFINITIONS)
    tools.extend(audit_log.TOOL_DEFINITIONS)
    tools.extend(market_data.TOOL_DEFINITIONS)
    tools.extend(exchange_adapter.TOOL_DEFINITIONS)
    tools.extend(risk_monitor.TOOL_DEFINITIONS)
    tools.extend(onchain_monitor.TOOL_DEFINITIONS)
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
    if name in tx_assistant.TOOL_NAMES:
        return tx_assistant.call_tool(name, args)
    if name in trc20_assistant.TOOL_NAMES:
        return trc20_assistant.call_tool(name, args)
    if name in agent_pipeline.TOOL_NAMES:
        return agent_pipeline.call_tool(name, args)
    if name in local_signer.TOOL_NAMES:
        return local_signer.call_tool(name, args)
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
    raise ValidationError(f"Unknown tool name: {name}")
