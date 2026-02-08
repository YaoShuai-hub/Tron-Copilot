"""Risk monitor module: position alerts + entry assistance."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from tron_mcp import safety, settings
from tron_mcp.modules import exchange_adapter, market_data
from tron_mcp.modules.notify_telegram import send_telegram, telegram_broadcast
from tron_mcp.utils.errors import ValidationError


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "position_snapshot",
        "description": "Fetch balances/positions and compute exposure snapshot.",
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
                "quote_asset": {"type": "string", "description": "Default: from rules (USDT)"},
                "include_positions": {"type": "boolean"},
                "rules_path": {"type": "string"},
            },
            "required": ["exchange_id"],
        },
    },
    {
        "name": "position_alerts",
        "description": "Generate position risk alerts based on rules.",
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
                "quote_asset": {"type": "string"},
                "rules_path": {"type": "string"},
                "notify": {"type": "boolean"},
                "chat_id": {"type": "string"},
                "broadcast": {"type": "boolean"},
            },
            "required": ["exchange_id"],
        },
    },
    {
        "name": "entry_assist",
        "description": "Provide entry hints based on orderbook/kline and rules.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "e.g., BTCUSDT"},
                "orderbook_limit": {"type": "integer"},
                "kline_interval": {"type": "string"},
                "kline_limit": {"type": "integer"},
                "rules_path": {"type": "string"},
                "notify": {"type": "boolean"},
                "chat_id": {"type": "string"},
                "broadcast": {"type": "boolean"},
            },
            "required": ["symbol"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def _default_rules() -> Dict[str, Any]:
    return {
        "quote_asset": "USDT",
        "stable_assets": ["USDT", "USDC", "USD", "FDUSD", "DAI"],
        "min_quote_free": 50.0,
        "min_quote_ratio": 0.2,
        "max_single_asset_ratio": 0.35,
        "max_quote_used_ratio": 0.8,
        "positions": {
            "enable": True,
            "max_unrealized_loss_pct": -0.05,
            "max_leverage": 5.0,
            "max_position_notional_ratio": 0.5,
            "max_open_orders": 50,
        },
        "entry": {
            "max_spread_bps": 15.0,
            "max_volatility_pct": 2.0,
            "min_depth_quote": 10000.0,
            "orderbook_limit": 20,
            "kline_interval": "1m",
            "kline_limit": 20,
        },
    }


def _rules_path(path: Optional[str]) -> Path:
    base = settings.SETTINGS.__dict__.get("risk_rules_path") or "risk_rules.json"
    return Path(path or base)


def _merge_rules(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge_rules(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _load_rules(path: Optional[str] = None) -> Dict[str, Any]:
    rules = _default_rules()
    rules_path = _rules_path(path)
    if rules_path.exists():
        try:
            data = json.loads(rules_path.read_text())
            if isinstance(data, dict):
                rules = _merge_rules(rules, data)
        except Exception:
            pass
    rules["rules_path"] = str(rules_path)
    return rules


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except Exception:
        return 0.0


def _normalize_pct(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        pct = float(value)
    except Exception:
        return None
    # CCXT often returns percentage in percent units (e.g., -3.2)
    if pct > 1 or pct < -1:
        pct = pct / 100.0
    return pct


def _resolve_exchange_creds(exchange_id: Optional[str]) -> tuple[Dict[str, Any], str]:
    creds = exchange_adapter._resolve_creds()
    resolved_id = creds.get("exchange_id")
    if not resolved_id:
        raise ValidationError("EXCHANGE_ID not found in .env.private")
    if exchange_id and exchange_id != resolved_id:
        raise ValidationError("exchange_id mismatch; update EXCHANGE_ID in .env.private")
    return creds, resolved_id


def _position_notional(pos: Dict[str, Any]) -> Optional[float]:
    notional = pos.get("notional") or pos.get("info", {}).get("notional")
    if notional is not None:
        return _safe_float(notional)
    contracts = _safe_float(pos.get("contracts") or pos.get("contractSize") or pos.get("positionAmt") or 0)
    mark_price = _safe_float(pos.get("markPrice") or pos.get("last") or pos.get("entryPrice") or 0)
    if contracts and mark_price:
        return abs(contracts) * mark_price
    return None


def _extract_positions(ex: Any) -> tuple[list[dict], Optional[str]]:
    if not hasattr(ex, "fetch_positions"):
        return [], "fetch_positions not supported"
    try:
        raw = ex.fetch_positions()
    except Exception as err:  # noqa: BLE001
        return [], str(err)

    positions: List[Dict[str, Any]] = []
    for pos in raw or []:
        symbol = pos.get("symbol") or pos.get("info", {}).get("symbol")
        side = pos.get("side")
        contracts = _safe_float(pos.get("contracts") or pos.get("positionAmt") or 0)
        leverage = _safe_float(pos.get("leverage") or pos.get("info", {}).get("leverage") or 0)
        pnl = _safe_float(pos.get("unrealizedPnl") or pos.get("info", {}).get("unrealizedPnl") or 0)
        pct = _normalize_pct(pos.get("percentage") or pos.get("info", {}).get("percentage"))
        notional = _position_notional(pos)
        if notional is None and contracts == 0:
            continue
        positions.append(
            {
                "symbol": symbol,
                "side": side,
                "contracts": contracts,
                "notional": notional,
                "leverage": leverage or None,
                "unrealizedPnl": pnl or None,
                "percentage": pct,
                "raw": pos,
            }
        )
    return positions, None


def _fetch_open_orders_count(ex: Any) -> tuple[Optional[int], Optional[str]]:
    if not hasattr(ex, "fetch_open_orders"):
        return None, "fetch_open_orders not supported"
    try:
        orders = ex.fetch_open_orders()
        return len(orders or []), None
    except Exception as err:  # noqa: BLE001
        return None, str(err)


def _price_for_asset(ex: Any, asset: str, quote: str, stable_assets: List[str], markets: Dict[str, Any]) -> Optional[float]:
    if asset == quote:
        return 1.0
    if asset in stable_assets and quote in stable_assets:
        return 1.0

    symbol = f"{asset}/{quote}"
    if symbol in markets:
        ticker = ex.fetch_ticker(symbol)
        price = _safe_float(ticker.get("last") or ticker.get("close"))
        return price if price > 0 else None

    inverse = f"{quote}/{asset}"
    if inverse in markets:
        ticker = ex.fetch_ticker(inverse)
        price = _safe_float(ticker.get("last") or ticker.get("close"))
        return (1.0 / price) if price > 0 else None

    return None


def position_snapshot(
    exchange_id: Optional[str],
    api_key: Optional[str] = None,
    secret: Optional[str] = None,
    password: Optional[str] = None,
    api_domain: Optional[str] = None,
    proxy: Optional[str] = None,
    sandbox: bool = False,
    quote_asset: Optional[str] = None,
    include_positions: bool = False,
    rules_path: Optional[str] = None,
) -> Dict[str, Any]:
    creds, exchange_id = _resolve_exchange_creds(exchange_id)
    rules = _load_rules(rules_path)
    quote_asset = (quote_asset or rules.get("quote_asset") or "USDT").upper()
    stable_assets = [str(a).upper() for a in rules.get("stable_assets") or []]
    sandbox = sandbox or bool(creds.get("sandbox"))
    ex = exchange_adapter._init_exchange(
        creds["exchange_id"],
        creds["api_key"],
        creds["secret"],
        creds["password"],
        creds["api_domain"],
        creds["proxy"],
        sandbox,
    )

    balance = ex.fetch_balance()
    totals = balance.get("total") or {}
    frees = balance.get("free") or {}
    used = balance.get("used") or {}

    markets = {}
    try:
        markets = ex.load_markets()
    except Exception:
        markets = {}

    assets: List[Dict[str, Any]] = []
    equity_total = 0.0
    missing_prices: List[str] = []

    for asset, total in totals.items():
        total_f = _safe_float(total)
        free_f = _safe_float(frees.get(asset))
        used_f = _safe_float(used.get(asset))
        if total_f == 0.0 and free_f == 0.0 and used_f == 0.0:
            continue
        asset_upper = str(asset).upper()
        price = None
        value_quote = None
        try:
            price = _price_for_asset(ex, asset_upper, quote_asset, stable_assets, markets)
            if price is not None:
                value_quote = total_f * price
                equity_total += value_quote
            else:
                missing_prices.append(asset_upper)
        except Exception:
            missing_prices.append(asset_upper)

        assets.append(
            {
                "asset": asset_upper,
                "total": total_f,
                "free": free_f,
                "used": used_f,
                "price": price,
                "valueQuote": value_quote,
            }
        )

    if quote_asset not in totals:
        # Ensure quote asset entry exists for clarity
        assets.append(
            {
                "asset": quote_asset,
                "total": _safe_float(totals.get(quote_asset)),
                "free": _safe_float(frees.get(quote_asset)),
                "used": _safe_float(used.get(quote_asset)),
                "price": 1.0,
                "valueQuote": _safe_float(totals.get(quote_asset)),
            }
        )

    for row in assets:
        value_quote = row.get("valueQuote")
        if value_quote is not None and equity_total > 0:
            row["ratio"] = value_quote / equity_total
        else:
            row["ratio"] = None

    assets.sort(key=lambda x: x.get("valueQuote") or 0.0, reverse=True)

    positions = None
    positions_error = None
    if include_positions and hasattr(ex, "fetch_positions"):
        try:
            positions = ex.fetch_positions()
        except Exception as err:  # noqa: BLE001
            positions_error = str(err)

    return {
        "exchange": exchange_id,
        "quoteAsset": quote_asset,
        "equity": {
            "totalQuote": equity_total if equity_total > 0 else None,
            "missingPrices": missing_prices,
            "complete": len(missing_prices) == 0 and equity_total > 0,
        },
        "balances": assets,
        "positions": positions,
        "positionsError": positions_error,
        "rulesPath": rules.get("rules_path"),
    }


def position_alerts(
    exchange_id: Optional[str],
    api_key: Optional[str] = None,
    secret: Optional[str] = None,
    password: Optional[str] = None,
    api_domain: Optional[str] = None,
    proxy: Optional[str] = None,
    sandbox: bool = False,
    quote_asset: Optional[str] = None,
    rules_path: Optional[str] = None,
    notify: bool = False,
    chat_id: Optional[str] = None,
    broadcast: bool = False,
) -> Dict[str, Any]:
    rules = _load_rules(rules_path)
    creds, exchange_id = _resolve_exchange_creds(exchange_id)
    sandbox = sandbox or bool(creds.get("sandbox"))
    snapshot = position_snapshot(
        exchange_id=exchange_id,
        api_key=api_key,
        secret=secret,
        password=password,
        api_domain=api_domain,
        proxy=proxy,
        sandbox=sandbox,
        quote_asset=quote_asset,
        include_positions=False,
        rules_path=rules_path,
    )

    quote = snapshot.get("quoteAsset")
    alerts: List[Dict[str, Any]] = []

    min_quote_free = _safe_float(rules.get("min_quote_free"))
    min_quote_ratio = _safe_float(rules.get("min_quote_ratio"))
    max_single_asset_ratio = _safe_float(rules.get("max_single_asset_ratio"))
    max_quote_used_ratio = _safe_float(rules.get("max_quote_used_ratio"))
    position_rules = rules.get("positions") or {}

    quote_row = next((a for a in snapshot["balances"] if a.get("asset") == quote), None)
    if quote_row:
        if min_quote_free and quote_row.get("free", 0) < min_quote_free:
            alerts.append(
                {
                    "level": "warning",
                    "code": "LOW_QUOTE_FREE",
                    "message": f"{quote} free below {min_quote_free}",
                    "value": quote_row.get("free"),
                }
            )
        total = quote_row.get("total") or 0.0
        used = quote_row.get("used") or 0.0
        if total > 0 and max_quote_used_ratio and (used / total) > max_quote_used_ratio:
            alerts.append(
                {
                    "level": "warning",
                    "code": "HIGH_QUOTE_USED",
                    "message": f"{quote} used ratio above {max_quote_used_ratio:.2f}",
                    "value": used / total,
                }
            )

    equity = snapshot.get("equity") or {}
    if equity.get("totalQuote"):
        total_quote = float(equity["totalQuote"])
        if min_quote_ratio and quote_row and total_quote > 0:
            quote_ratio = (quote_row.get("valueQuote") or 0.0) / total_quote
            if quote_ratio < min_quote_ratio:
                alerts.append(
                    {
                        "level": "warning",
                        "code": "LOW_QUOTE_RATIO",
                        "message": f"{quote} ratio below {min_quote_ratio:.2f}",
                        "value": quote_ratio,
                    }
                )

        if max_single_asset_ratio:
            for row in snapshot["balances"]:
                ratio = row.get("ratio")
                if ratio is None or row.get("asset") == quote:
                    continue
                if ratio > max_single_asset_ratio:
                    alerts.append(
                        {
                            "level": "warning",
                            "code": "HIGH_SINGLE_ASSET",
                            "message": f"{row.get('asset')} ratio above {max_single_asset_ratio:.2f}",
                            "value": ratio,
                        }
                    )

    positions: List[Dict[str, Any]] = []
    positions_error = None
    open_orders_count = None
    open_orders_error = None

    if position_rules.get("enable", True):
        try:
            creds, exchange_id = _resolve_exchange_creds(exchange_id)
            ex = exchange_adapter._init_exchange(
                creds["exchange_id"],
                creds["api_key"],
                creds["secret"],
                creds["password"],
                creds["api_domain"],
                creds["proxy"],
                sandbox,
            )
            positions, positions_error = _extract_positions(ex)
            open_orders_count, open_orders_error = _fetch_open_orders_count(ex)
        except Exception as err:  # noqa: BLE001
            positions_error = str(err)

    max_loss_pct = _normalize_pct(position_rules.get("max_unrealized_loss_pct"))
    max_leverage = _safe_float(position_rules.get("max_leverage"))
    max_notional_ratio = _safe_float(position_rules.get("max_position_notional_ratio"))
    max_open_orders = int(position_rules.get("max_open_orders") or 0)

    if max_open_orders and open_orders_count is not None and open_orders_count > max_open_orders:
        alerts.append(
            {
                "level": "warning",
                "code": "TOO_MANY_OPEN_ORDERS",
                "message": f"open orders {open_orders_count} > {max_open_orders}",
                "value": open_orders_count,
            }
        )

    for pos in positions:
        symbol = pos.get("symbol") or "UNKNOWN"
        pct = pos.get("percentage")
        if max_loss_pct is not None and pct is not None and pct < max_loss_pct:
            alerts.append(
                {
                    "level": "warning",
                    "code": "POSITION_LOSS",
                    "message": f"{symbol} loss {pct:.2%} < {max_loss_pct:.2%}",
                    "value": pct,
                }
            )
        lev = pos.get("leverage")
        if max_leverage and lev and lev > max_leverage:
            alerts.append(
                {
                    "level": "warning",
                    "code": "HIGH_LEVERAGE",
                    "message": f"{symbol} leverage {lev} > {max_leverage}",
                    "value": lev,
                }
            )
        notional = pos.get("notional")
        if max_notional_ratio and notional and equity.get("totalQuote"):
            ratio = notional / float(equity["totalQuote"])
            if ratio > max_notional_ratio:
                alerts.append(
                    {
                        "level": "warning",
                        "code": "HIGH_POSITION_NOTIONAL",
                        "message": f"{symbol} notional ratio {ratio:.2%} > {max_notional_ratio:.2%}",
                        "value": ratio,
                    }
                )

    if notify and alerts:
        title = f"Position Alerts ({exchange_id})"
        lines = [title]
        for item in alerts[:8]:
            lines.append(f"- {item['code']}: {item['message']}")
        msg = "\n".join(lines)
        if broadcast:
            telegram_broadcast(msg)
        else:
            send_telegram(msg, chat_id=chat_id)

    return {
        "exchange": exchange_id,
        "alerts": alerts,
        "snapshot": snapshot,
        "rules": rules,
        "positions": positions,
        "positionsError": positions_error,
        "openOrdersCount": open_orders_count,
        "openOrdersError": open_orders_error,
    }


def _compute_depth_quote(levels: List[List[Any]], limit: int) -> float:
    depth = 0.0
    for price, qty in levels[:limit]:
        depth += _safe_float(price) * _safe_float(qty)
    return depth


def entry_assist(
    symbol: str,
    orderbook_limit: Optional[int] = None,
    kline_interval: Optional[str] = None,
    kline_limit: Optional[int] = None,
    rules_path: Optional[str] = None,
    notify: bool = False,
    chat_id: Optional[str] = None,
    broadcast: bool = False,
) -> Dict[str, Any]:
    if not symbol:
        raise ValidationError("symbol is required")
    rules = _load_rules(rules_path)
    entry_rules = rules.get("entry") or {}

    orderbook_limit = int(orderbook_limit or entry_rules.get("orderbook_limit") or 20)
    kline_interval = str(kline_interval or entry_rules.get("kline_interval") or "1m")
    kline_limit = int(kline_limit or entry_rules.get("kline_limit") or 20)

    orderbook = market_data.get_orderbook(symbol=symbol, limit=orderbook_limit)
    kline = market_data.get_kline(symbol=symbol, interval=kline_interval, limit=kline_limit)

    best_bid = orderbook.get("bestBid")
    best_ask = orderbook.get("bestAsk")
    mid = orderbook.get("mid")
    spread = orderbook.get("spread")
    spread_bps = None
    if mid and spread:
        spread_bps = (spread / mid) * 10000

    bids = orderbook.get("bids") or []
    asks = orderbook.get("asks") or []
    depth_limit = min(10, orderbook_limit)
    depth_quote = _compute_depth_quote(bids, depth_limit) + _compute_depth_quote(asks, depth_limit)

    candles = kline.get("candles") or []
    volatility_pct = None
    last_close = None
    if candles:
        last = candles[-1]
        high = _safe_float(last.get("high"))
        low = _safe_float(last.get("low"))
        close = _safe_float(last.get("close"))
        last_close = close
        if close > 0:
            volatility_pct = (high - low) / close * 100

    alerts: List[Dict[str, Any]] = []
    max_spread_bps = _safe_float(entry_rules.get("max_spread_bps"))
    max_volatility_pct = _safe_float(entry_rules.get("max_volatility_pct"))
    min_depth_quote = _safe_float(entry_rules.get("min_depth_quote"))

    if spread_bps is not None and max_spread_bps and spread_bps > max_spread_bps:
        alerts.append(
            {
                "level": "warning",
                "code": "WIDE_SPREAD",
                "message": f"spread {spread_bps:.2f} bps > {max_spread_bps:.2f}",
                "value": spread_bps,
            }
        )
    if volatility_pct is not None and max_volatility_pct and volatility_pct > max_volatility_pct:
        alerts.append(
            {
                "level": "warning",
                "code": "HIGH_VOL",
                "message": f"volatility {volatility_pct:.2f}% > {max_volatility_pct:.2f}%",
                "value": volatility_pct,
            }
        )
    if min_depth_quote and depth_quote < min_depth_quote:
        alerts.append(
            {
                "level": "warning",
                "code": "LOW_DEPTH",
                "message": f"depth {depth_quote:.2f} < {min_depth_quote:.2f}",
                "value": depth_quote,
            }
        )

    signal = "OK" if not alerts else "CAUTION"

    if notify:
        msg = (
            f"Entry Assist {symbol}\n"
            f"Spread(bps): {spread_bps}\n"
            f"Volatility(%): {volatility_pct}\n"
            f"Depth(quote): {depth_quote}\n"
            f"Signal: {signal}"
        )
        if broadcast:
            telegram_broadcast(msg)
        else:
            send_telegram(msg, chat_id=chat_id)

    return {
        "symbol": symbol,
        "spreadBps": spread_bps,
        "volatilityPct": volatility_pct,
        "depthQuote": depth_quote,
        "lastClose": last_close,
        "signal": signal,
        "alerts": alerts,
        "rules": rules,
    }


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "position_snapshot":
        return position_snapshot(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            quote_asset=args.get("quote_asset"),
            include_positions=bool(args.get("include_positions")),
            rules_path=args.get("rules_path"),
        )
    if name == "position_alerts":
        return position_alerts(
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            sandbox=bool(args.get("sandbox")),
            quote_asset=args.get("quote_asset"),
            rules_path=args.get("rules_path"),
            notify=bool(args.get("notify")),
            chat_id=args.get("chat_id"),
            broadcast=bool(args.get("broadcast")),
        )
    if name == "entry_assist":
        return entry_assist(
            symbol=args.get("symbol"),
            orderbook_limit=args.get("orderbook_limit"),
            kline_interval=args.get("kline_interval"),
            kline_limit=args.get("kline_limit"),
            rules_path=args.get("rules_path"),
            notify=bool(args.get("notify")),
            chat_id=args.get("chat_id"),
            broadcast=bool(args.get("broadcast")),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="position_snapshot", description="Fetch balances/positions and compute exposure snapshot.")
    def tool_position_snapshot(
        exchange_id: str,
        api_key: str | None = None,
        secret: str | None = None,
        password: str | None = None,
        api_domain: str | None = None,
        proxy: str | None = None,
        sandbox: bool = False,
        quote_asset: str | None = None,
        include_positions: bool = False,
        rules_path: str | None = None,
    ) -> dict:
        return safety.enrich(
            position_snapshot(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
                quote_asset=quote_asset,
                include_positions=include_positions,
                rules_path=rules_path,
            )
        )

    @mcp.tool(name="position_alerts", description="Generate position risk alerts based on rules.")
    def tool_position_alerts(
        exchange_id: str,
        api_key: str | None = None,
        secret: str | None = None,
        password: str | None = None,
        api_domain: str | None = None,
        proxy: str | None = None,
        sandbox: bool = False,
        quote_asset: str | None = None,
        rules_path: str | None = None,
        notify: bool = False,
        chat_id: str | None = None,
        broadcast: bool = False,
    ) -> dict:
        return safety.enrich(
            position_alerts(
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                sandbox=sandbox,
                quote_asset=quote_asset,
                rules_path=rules_path,
                notify=notify,
                chat_id=chat_id,
                broadcast=broadcast,
            )
        )

    @mcp.tool(name="entry_assist", description="Provide entry hints based on orderbook/kline and rules.")
    def tool_entry_assist(
        symbol: str,
        orderbook_limit: int | None = None,
        kline_interval: str | None = None,
        kline_limit: int | None = None,
        rules_path: str | None = None,
        notify: bool = False,
        chat_id: str | None = None,
        broadcast: bool = False,
    ) -> dict:
        return safety.enrich(
            entry_assist(
                symbol=symbol,
                orderbook_limit=orderbook_limit,
                kline_interval=kline_interval,
                kline_limit=kline_limit,
                rules_path=rules_path,
                notify=notify,
                chat_id=chat_id,
                broadcast=broadcast,
            )
        )
