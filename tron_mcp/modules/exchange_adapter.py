"""Unified exchange adapter using CCXT (Task 3)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
import re

from tron_mcp import safety, settings
from tron_mcp.utils.errors import ValidationError, UpstreamError


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "exchange_get_balance",
        "description": "Get balances from an exchange via CCXT.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "exchange_get_asset_balance",
        "description": "Get balance for a single currency via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {"currency": {"type": "string", "description": "e.g., USDT"}},
            "required": ["currency"],
        },
    },
    {
        "name": "exchange_get_deposit_address",
        "description": "Get deposit address from an exchange via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "currency": {"type": "string", "description": "e.g., USDT"},
                "network": {"type": "string", "description": "e.g., TRC20/ERC20/BEP20"},
                "params": {"type": "object"},
            },
            "required": ["currency"],
        },
    },
    {
        "name": "exchange_withdraw",
        "description": "Withdraw funds from an exchange via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "currency": {"type": "string", "description": "e.g., USDT"},
                "amount": {"type": "number"},
                "address": {"type": "string"},
                "tag": {"type": "string", "description": "memo/tag for some networks"},
                "network": {"type": "string", "description": "e.g., TRC20/ERC20/BEP20"},
                "params": {"type": "object"},
            },
            "required": ["currency", "amount", "address"],
        },
    },
    {
        "name": "exchange_fetch_withdrawals",
        "description": "Fetch recent withdrawals via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "currency": {"type": "string"},
                "since": {"type": "integer", "description": "Unix ms"},
                "limit": {"type": "integer"},
                "params": {"type": "object"},
            },
            "required": [],
        },
    },
    {
        "name": "exchange_fetch_deposits",
        "description": "Fetch recent deposits via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "currency": {"type": "string"},
                "since": {"type": "integer", "description": "Unix ms"},
                "limit": {"type": "integer"},
                "params": {"type": "object"},
            },
            "required": [],
        },
    },
    {
        "name": "exchange_create_order",
        "description": "Create an order via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string"},
                "type": {"type": "string", "description": "market or limit"},
                "side": {"type": "string", "description": "buy or sell"},
                "amount": {"type": "number"},
                "price": {"type": "number"},
                "params": {"type": "object"},
            },
            "required": ["symbol", "type", "side", "amount"],
        },
    },
    {
        "name": "exchange_cancel_order",
        "description": "Cancel an order via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "symbol": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "exchange_fetch_order",
        "description": "Fetch an order via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "symbol": {"type": "string"},
                "params": {"type": "object"},
            },
            "required": ["order_id"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}

TRON_B58_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")
EVM_HEX_RE = re.compile(r"^0x[a-fA-F0-9]{40}$")


def _parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y", "on"}
    return bool(value)


def _parse_float(value: Any, field: str, allow_none: bool = False) -> Optional[float]:
    if value in (None, ""):
        if allow_none:
            return None
        raise ValidationError(f"{field} is required")
    try:
        return float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{field} must be a number") from None


def _load_env_private(path: Path) -> dict:
    env = {}
    if not path.exists():
        return env
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _require_ccxt() -> Any:
    try:
        import ccxt  # type: ignore

        return ccxt
    except Exception as err:  # noqa: BLE001
        raise ValidationError(f"ccxt not installed: {err}. Install with: pip install ccxt") from err


def _resolve_creds() -> Dict[str, Optional[str]]:
    env = _load_env_private(Path(".env.private"))
    exchange_id = env.get("EXCHANGE_ID")
    api_key = env.get("EXCHANGE_API_KEY")
    secret = env.get("EXCHANGE_SECRET")
    password = env.get("EXCHANGE_PASSWORD")
    api_domain = env.get("EXCHANGE_API_DOMAIN")
    proxy = env.get("EXCHANGE_PROXY")
    sandbox = _parse_bool(env.get("EXCHANGE_SANDBOX"))

    if not exchange_id:
        raise ValidationError("EXCHANGE_ID not found in .env.private")
    return {
        "exchange_id": exchange_id,
        "api_key": api_key,
        "secret": secret,
        "password": password,
        "api_domain": api_domain,
        "proxy": proxy,
        "sandbox": sandbox,
    }


def _apply_binance_domain(ex: Any, api_domain: str) -> None:
    base = api_domain.strip()
    if not base:
        return
    if not base.startswith("http"):
        base = f"https://{base}"
    base = base.rstrip("/")
    api_map = getattr(ex, "urls", {}).get("api")
    if isinstance(api_map, dict):
        for key, url in list(api_map.items()):
            try:
                parsed = urlparse(str(url))
                path = parsed.path if parsed.scheme and parsed.netloc else f"/{str(url).lstrip('/')}"
                api_map[key] = f"{base}{path}"
            except Exception:  # noqa: BLE001
                api_map[key] = f"{base}/{str(url).lstrip('/')}"
        ex.urls["api"] = api_map
    else:
        ex.urls["api"] = f"{base}/api"


def _binance_hint(exchange_id: Optional[str]) -> str:
    if exchange_id and "binance" in exchange_id.lower():
        return (
            " Binance endpoint may be blocked (HTTP 451/timeout). "
            "Try EXCHANGE_API_DOMAIN=api1.binance.com or api2.binance.com or set EXCHANGE_PROXY."
        )
    return ""


def _infer_network(currency: Optional[str], address: Optional[str]) -> Optional[str]:
    if not address:
        return None
    if TRON_B58_RE.fullmatch(address):
        if currency and currency.upper() == "TRX":
            return "TRX"
        return "TRC20"
    if EVM_HEX_RE.fullmatch(address):
        # Ambiguous across EVM chains; require explicit network for safety.
        return None
    return None


def _init_exchange(
    exchange_id: str,
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
    sandbox: bool,
) -> Any:
    ccxt = _require_ccxt()
    if not hasattr(ccxt, exchange_id):
        raise ValidationError(f"Unsupported exchange_id: {exchange_id}")
    ex_class = getattr(ccxt, exchange_id)
    opts = {}
    if api_key:
        opts["apiKey"] = api_key
    if secret:
        opts["secret"] = secret
    if password:
        opts["password"] = password
    ex = ex_class(opts)
    if api_domain and exchange_id.startswith("binance"):
        _apply_binance_domain(ex, api_domain)
    if proxy:
        proxy = proxy.strip()
        if proxy.startswith("socks4://") or proxy.startswith("socks5://"):
            ex.socks_proxy = proxy
        else:
            ex.http_proxy = proxy
            ex.https_proxy = proxy
    if sandbox and hasattr(ex, "set_sandbox_mode"):
        ex.set_sandbox_mode(True)
    return ex


def exchange_get_balance() -> Dict[str, Any]:
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        return ex.fetch_balance()
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_get_balance failed: {err}.{hint}") from err


def _extract_currency_balance(balance: Dict[str, Any], currency: str) -> Dict[str, Any]:
    code = (currency or "").upper()
    if not code:
        raise ValidationError("currency is required")

    entry = balance.get(code)
    if not isinstance(entry, dict):
        entry = {}

    total_map = balance.get("total") or {}
    free_map = balance.get("free") or {}
    used_map = balance.get("used") or {}

    total = entry.get("total")
    free = entry.get("free")
    used = entry.get("used")

    if total is None:
        total = total_map.get(code)
    if free is None:
        free = free_map.get(code)
    if used is None:
        used = used_map.get(code)

    return {
        "currency": code,
        "free": free,
        "used": used,
        "total": total,
        "raw": entry,
    }


def exchange_get_asset_balance(currency: str | None = None) -> Dict[str, Any]:
    if not currency:
        raise ValidationError("currency is required")
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        balance = ex.fetch_balance()
        return {
            "exchange": creds.get("exchange_id"),
            "balance": _extract_currency_balance(balance, currency),
        }
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_get_asset_balance failed: {err}.{hint}") from err


def exchange_get_deposit_address(
    currency: str,
    network: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not currency:
        raise ValidationError("currency is required")
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        extra = dict(params or {})
        if network:
            extra.setdefault("network", network)
        return ex.fetch_deposit_address(currency, extra)
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_get_deposit_address failed: {err}.{hint}") from err


def exchange_withdraw(
    currency: str,
    amount: float | int | str,
    address: str,
    tag: Optional[str] = None,
    network: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not currency:
        raise ValidationError("currency is required")
    if not address:
        raise ValidationError("address is required")
    amount_value = _parse_float(amount, "amount")
    if amount_value <= 0:
        raise ValidationError("amount must be > 0")
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        inferred = None
        if not network:
            inferred = _infer_network(currency, address)
            if inferred:
                network = inferred
        extra = dict(params or {})
        if network:
            extra.setdefault("network", network)
        result = ex.withdraw(currency, amount_value, address, tag, extra)
        if inferred and isinstance(result, dict):
            result["inferredNetwork"] = inferred
        return result
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_withdraw failed: {err}.{hint}") from err


def exchange_fetch_withdrawals(
    currency: Optional[str] = None,
    since: Optional[int] = None,
    limit: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        return {
            "exchange": creds.get("exchange_id"),
            "items": ex.fetch_withdrawals(currency, since, limit, params or {}),
        }
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_fetch_withdrawals failed: {err}.{hint}") from err


def exchange_fetch_deposits(
    currency: Optional[str] = None,
    since: Optional[int] = None,
    limit: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        return {
            "exchange": creds.get("exchange_id"),
            "items": ex.fetch_deposits(currency, since, limit, params or {}),
        }
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_fetch_deposits failed: {err}.{hint}") from err


def exchange_create_order(
    symbol: str,
    type: str,
    side: str,
    amount: float | int | str,
    price: Optional[float | int | str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    amount_value = _parse_float(amount, "amount")
    if amount_value <= 0:
        raise ValidationError("amount must be > 0")
    price_value = _parse_float(price, "price", allow_none=True)
    if price_value is not None and price_value <= 0:
        raise ValidationError("price must be > 0")
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        return ex.create_order(symbol, type, side, amount_value, price_value, params or {})
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_create_order failed: {err}.{hint}") from err


def exchange_cancel_order(
    order_id: str,
    symbol: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        return ex.cancel_order(order_id, symbol, params or {})
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_cancel_order failed: {err}.{hint}") from err


def exchange_fetch_order(
    order_id: str,
    symbol: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds()
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        bool(creds.get("sandbox")),
    )
    try:
        return ex.fetch_order(order_id, symbol, params or {})
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_fetch_order failed: {err}.{hint}") from err


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "exchange_get_balance":
        return exchange_get_balance()
    if name == "exchange_get_asset_balance":
        return exchange_get_asset_balance(currency=args.get("currency"))
    if name == "exchange_get_deposit_address":
        return exchange_get_deposit_address(
            currency=args.get("currency"),
            network=args.get("network"),
            params=args.get("params"),
        )
    if name == "exchange_withdraw":
        return exchange_withdraw(
            currency=args.get("currency"),
            amount=args.get("amount"),
            address=args.get("address"),
            tag=args.get("tag"),
            network=args.get("network"),
            params=args.get("params"),
        )
    if name == "exchange_fetch_withdrawals":
        return exchange_fetch_withdrawals(
            currency=args.get("currency"),
            since=args.get("since"),
            limit=args.get("limit"),
            params=args.get("params"),
        )
    if name == "exchange_fetch_deposits":
        return exchange_fetch_deposits(
            currency=args.get("currency"),
            since=args.get("since"),
            limit=args.get("limit"),
            params=args.get("params"),
        )
    if name == "exchange_create_order":
        return exchange_create_order(
            symbol=args.get("symbol"),
            type=args.get("type"),
            side=args.get("side"),
            amount=args.get("amount"),
            price=args.get("price"),
            params=args.get("params"),
        )
    if name == "exchange_cancel_order":
        return exchange_cancel_order(
            order_id=args.get("order_id"),
            symbol=args.get("symbol"),
            params=args.get("params"),
        )
    if name == "exchange_fetch_order":
        return exchange_fetch_order(
            order_id=args.get("order_id"),
            symbol=args.get("symbol"),
            params=args.get("params"),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="exchange_get_balance", description="Get balances from an exchange via CCXT.")
    def tool_exchange_get_balance() -> dict:
        return safety.enrich(exchange_get_balance())

    @mcp.tool(name="exchange_get_asset_balance", description="Get single-currency balance via CCXT.")
    def tool_exchange_get_asset_balance(currency: str | None = None) -> dict:
        return safety.enrich(exchange_get_asset_balance(currency=currency))

    @mcp.tool(name="exchange_get_deposit_address", description="Get deposit address via CCXT.")
    def tool_exchange_get_deposit_address(
        currency: str,
        network: str | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_get_deposit_address(currency=currency, network=network, params=params)
        )

    @mcp.tool(name="exchange_withdraw", description="Withdraw funds via CCXT.")
    def tool_exchange_withdraw(
        currency: str,
        amount: float,
        address: str,
        tag: str | None = None,
        network: str | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_withdraw(
                currency=currency,
                amount=amount,
                address=address,
                tag=tag,
                network=network,
                params=params,
            )
        )

    @mcp.tool(name="exchange_fetch_withdrawals", description="Fetch withdrawals via CCXT.")
    def tool_exchange_fetch_withdrawals(
        currency: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_fetch_withdrawals(currency=currency, since=since, limit=limit, params=params)
        )

    @mcp.tool(name="exchange_fetch_deposits", description="Fetch deposits via CCXT.")
    def tool_exchange_fetch_deposits(
        currency: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_fetch_deposits(currency=currency, since=since, limit=limit, params=params)
        )

    @mcp.tool(name="exchange_create_order", description="Create an order via CCXT.")
    def tool_exchange_create_order(
        symbol: str,
        type: str,
        side: str,
        amount: float,
        price: float | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_create_order(
                symbol=symbol,
                type=type,
                side=side,
                amount=amount,
                price=price,
                params=params,
            )
        )

    @mcp.tool(name="exchange_cancel_order", description="Cancel an order via CCXT.")
    def tool_exchange_cancel_order(
        order_id: str,
        symbol: str | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_cancel_order(order_id=order_id, symbol=symbol, params=params)
        )

    @mcp.tool(name="exchange_fetch_order", description="Fetch an order via CCXT.")
    def tool_exchange_fetch_order(
        order_id: str,
        symbol: str | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_fetch_order(order_id=order_id, symbol=symbol, params=params)
        )
