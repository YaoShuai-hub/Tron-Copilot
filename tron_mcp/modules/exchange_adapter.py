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
        "inputSchema": {
            "type": "object",
            "properties": {
                "exchange_id": {"type": "string", "description": "e.g., binance, okx"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string", "description": "Override API domain (binance only)"},
                "proxy": {"type": "string", "description": "Proxy URL, e.g. http://127.0.0.1:7890"},
                "sandbox": {"type": "boolean"},
            },
            "required": [],
        },
    },
    {
        "name": "exchange_get_deposit_address",
        "description": "Get deposit address from an exchange via CCXT.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "exchange_id": {"type": "string"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string"},
                "proxy": {"type": "string"},
                "sandbox": {"type": "boolean"},
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
                "exchange_id": {"type": "string"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string"},
                "proxy": {"type": "string"},
                "sandbox": {"type": "boolean"},
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
                "exchange_id": {"type": "string"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string"},
                "proxy": {"type": "string"},
                "sandbox": {"type": "boolean"},
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
                "exchange_id": {"type": "string"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string"},
                "proxy": {"type": "string"},
                "sandbox": {"type": "boolean"},
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
                "exchange_id": {"type": "string"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string"},
                "proxy": {"type": "string"},
                "sandbox": {"type": "boolean"},
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
                "exchange_id": {"type": "string"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string"},
                "proxy": {"type": "string"},
                "sandbox": {"type": "boolean"},
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
                "exchange_id": {"type": "string"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string"},
                "proxy": {"type": "string"},
                "sandbox": {"type": "boolean"},
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


def _resolve_creds(
    exchange_id: Optional[str],
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
) -> Dict[str, Optional[str]]:
    env = _load_env_private(Path(".env.private"))
    exchange_id = exchange_id or env.get("EXCHANGE_ID") or settings.SETTINGS.__dict__.get("exchange_id")
    api_key = api_key or env.get("EXCHANGE_API_KEY") or settings.SETTINGS.__dict__.get("exchange_api_key")
    secret = secret or env.get("EXCHANGE_SECRET") or settings.SETTINGS.__dict__.get("exchange_secret")
    password = password or env.get("EXCHANGE_PASSWORD") or settings.SETTINGS.__dict__.get("exchange_password")
    api_domain = api_domain or env.get("EXCHANGE_API_DOMAIN") or settings.SETTINGS.__dict__.get("exchange_api_domain")
    proxy = proxy or env.get("EXCHANGE_PROXY") or settings.SETTINGS.__dict__.get("exchange_proxy")

    if not exchange_id:
        raise ValidationError("exchange_id is required (or set EXCHANGE_ID)")
    return {
        "exchange_id": exchange_id,
        "api_key": api_key,
        "secret": secret,
        "password": password,
        "api_domain": api_domain,
        "proxy": proxy,
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


def exchange_get_balance(
    exchange_id: Optional[str] = None,
    api_key: Optional[str] = None,
    secret: Optional[str] = None,
    password: Optional[str] = None,
    api_domain: Optional[str] = None,
    proxy: Optional[str] = None,
    sandbox: bool = False,
) -> Dict[str, Any]:
    creds = _resolve_creds(exchange_id, api_key, secret, password, api_domain, proxy)
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
    )
    try:
        return ex.fetch_balance()
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_get_balance failed: {err}.{hint}") from err


def exchange_get_deposit_address(
    exchange_id: Optional[str],
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
    sandbox: bool,
    currency: str,
    network: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not currency:
        raise ValidationError("currency is required")
    creds = _resolve_creds(exchange_id, api_key, secret, password, api_domain, proxy)
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
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
    exchange_id: Optional[str],
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
    sandbox: bool,
    currency: str,
    amount: float,
    address: str,
    tag: Optional[str] = None,
    network: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not currency:
        raise ValidationError("currency is required")
    if not address:
        raise ValidationError("address is required")
    creds = _resolve_creds(exchange_id, api_key, secret, password, api_domain, proxy)
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
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
        result = ex.withdraw(currency, amount, address, tag, extra)
        if inferred and isinstance(result, dict):
            result["inferredNetwork"] = inferred
        return result
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_withdraw failed: {err}.{hint}") from err


def exchange_fetch_withdrawals(
    exchange_id: Optional[str],
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
    sandbox: bool,
    currency: Optional[str] = None,
    since: Optional[int] = None,
    limit: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds(exchange_id, api_key, secret, password, api_domain, proxy)
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
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
    exchange_id: Optional[str],
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
    sandbox: bool,
    currency: Optional[str] = None,
    since: Optional[int] = None,
    limit: Optional[int] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds(exchange_id, api_key, secret, password, api_domain, proxy)
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
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
    exchange_id: Optional[str],
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
    sandbox: bool,
    symbol: str,
    type: str,
    side: str,
    amount: float,
    price: Optional[float] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds(exchange_id, api_key, secret, password, api_domain, proxy)
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
    )
    try:
        return ex.create_order(symbol, type, side, amount, price, params or {})
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_create_order failed: {err}.{hint}") from err


def exchange_cancel_order(
    exchange_id: Optional[str],
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
    sandbox: bool,
    order_id: str,
    symbol: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds(exchange_id, api_key, secret, password, api_domain, proxy)
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
    )
    try:
        return ex.cancel_order(order_id, symbol, params or {})
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_cancel_order failed: {err}.{hint}") from err


def exchange_fetch_order(
    exchange_id: Optional[str],
    api_key: Optional[str],
    secret: Optional[str],
    password: Optional[str],
    api_domain: Optional[str],
    proxy: Optional[str],
    sandbox: bool,
    order_id: str,
    symbol: Optional[str] = None,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    creds = _resolve_creds(exchange_id, api_key, secret, password, api_domain, proxy)
    ex = _init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
    )
    try:
        return ex.fetch_order(order_id, symbol, params or {})
    except Exception as err:  # noqa: BLE001
        hint = _binance_hint(creds.get("exchange_id"))
        raise UpstreamError(f"exchange_fetch_order failed: {err}.{hint}") from err


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "exchange_get_balance":
        return exchange_get_balance(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
        )
    if name == "exchange_get_deposit_address":
        return exchange_get_deposit_address(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            currency=args.get("currency"),
            network=args.get("network"),
            params=args.get("params"),
        )
    if name == "exchange_withdraw":
        return exchange_withdraw(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            currency=args.get("currency"),
            amount=float(args.get("amount")),
            address=args.get("address"),
            tag=args.get("tag"),
            network=args.get("network"),
            params=args.get("params"),
        )
    if name == "exchange_fetch_withdrawals":
        return exchange_fetch_withdrawals(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            currency=args.get("currency"),
            since=args.get("since"),
            limit=args.get("limit"),
            params=args.get("params"),
        )
    if name == "exchange_fetch_deposits":
        return exchange_fetch_deposits(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            currency=args.get("currency"),
            since=args.get("since"),
            limit=args.get("limit"),
            params=args.get("params"),
        )
    if name == "exchange_create_order":
        return exchange_create_order(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            symbol=args.get("symbol"),
            type=args.get("type"),
            side=args.get("side"),
            amount=float(args.get("amount")),
            price=args.get("price"),
            params=args.get("params"),
        )
    if name == "exchange_cancel_order":
        return exchange_cancel_order(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            order_id=args.get("order_id"),
            symbol=args.get("symbol"),
            params=args.get("params"),
        )
    if name == "exchange_fetch_order":
        return exchange_fetch_order(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            order_id=args.get("order_id"),
            symbol=args.get("symbol"),
            params=args.get("params"),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="exchange_get_balance", description="Get balances from an exchange via CCXT.")
    def tool_exchange_get_balance(
        exchange_id: str | None = None,
        api_key: str | None = None,
        secret: str | None = None,
        password: str | None = None,
        api_domain: str | None = None,
        proxy: str | None = None,
        sandbox: bool = False,
    ) -> dict:
        return safety.enrich(
            exchange_get_balance(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
            )
        )

    @mcp.tool(name="exchange_get_deposit_address", description="Get deposit address via CCXT.")
    def tool_exchange_get_deposit_address(
        exchange_id: str | None,
        api_key: str | None,
        secret: str | None,
        password: str | None,
        api_domain: str | None,
        proxy: str | None,
        sandbox: bool,
        currency: str,
        network: str | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_get_deposit_address(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
                currency=currency,
                network=network,
                params=params,
            )
        )

    @mcp.tool(name="exchange_withdraw", description="Withdraw funds via CCXT.")
    def tool_exchange_withdraw(
        exchange_id: str | None,
        api_key: str | None,
        secret: str | None,
        password: str | None,
        api_domain: str | None,
        proxy: str | None,
        sandbox: bool,
        currency: str,
        amount: float,
        address: str,
        tag: str | None = None,
        network: str | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_withdraw(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
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
        exchange_id: str | None,
        api_key: str | None,
        secret: str | None,
        password: str | None,
        api_domain: str | None,
        proxy: str | None,
        sandbox: bool,
        currency: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_fetch_withdrawals(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
                currency=currency,
                since=since,
                limit=limit,
                params=params,
            )
        )

    @mcp.tool(name="exchange_fetch_deposits", description="Fetch deposits via CCXT.")
    def tool_exchange_fetch_deposits(
        exchange_id: str | None,
        api_key: str | None,
        secret: str | None,
        password: str | None,
        api_domain: str | None,
        proxy: str | None,
        sandbox: bool,
        currency: str | None = None,
        since: int | None = None,
        limit: int | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_fetch_deposits(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
                currency=currency,
                since=since,
                limit=limit,
                params=params,
            )
        )

    @mcp.tool(name="exchange_create_order", description="Create an order via CCXT.")
    def tool_exchange_create_order(
        exchange_id: str | None,
        api_key: str | None,
        secret: str | None,
        password: str | None,
        api_domain: str | None,
        proxy: str | None,
        sandbox: bool,
        symbol: str,
        type: str,
        side: str,
        amount: float,
        price: float | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_create_order(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
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
        exchange_id: str | None,
        api_key: str | None,
        secret: str | None,
        password: str | None,
        api_domain: str | None,
        proxy: str | None,
        sandbox: bool,
        order_id: str,
        symbol: str | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_cancel_order(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
                order_id=order_id,
                symbol=symbol,
                params=params,
            )
        )

    @mcp.tool(name="exchange_fetch_order", description="Fetch an order via CCXT.")
    def tool_exchange_fetch_order(
        exchange_id: str | None,
        api_key: str | None,
        secret: str | None,
        password: str | None,
        api_domain: str | None,
        proxy: str | None,
        sandbox: bool,
        order_id: str,
        symbol: str | None = None,
        params: dict | None = None,
    ) -> dict:
        return safety.enrich(
            exchange_fetch_order(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
                order_id=order_id,
                symbol=symbol,
                params=params,
            )
        )
