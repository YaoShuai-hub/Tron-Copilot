"""Market data module (Task 2): orderbook & kline via REST."""

from __future__ import annotations

import json
import urllib.request
from typing import Any, Dict, List, Optional

from tron_mcp import safety, settings
from tron_mcp.modules.notify_telegram import send_telegram, telegram_broadcast
from tron_mcp.utils.errors import ValidationError, UpstreamError


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "get_orderbook",
        "description": "Fetch orderbook snapshot (REST).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair, e.g. BTCUSDT"},
                "limit": {"type": "integer", "description": "Depth size"},
                "notify": {"type": "boolean", "description": "Send summary to Telegram"},
                "chat_id": {"type": "string", "description": "Optional chat id"},
                "broadcast": {"type": "boolean", "description": "Broadcast to subscribers"},
            },
            "required": [],
        },
    },
    {
        "name": "get_kline",
        "description": "Fetch kline data (REST).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "symbol": {"type": "string", "description": "Trading pair, e.g. BTCUSDT"},
                "interval": {"type": "string", "description": "1m/5m/1h/1d"},
                "limit": {"type": "integer", "description": "Number of candles"},
                "notify": {"type": "boolean", "description": "Send summary to Telegram"},
                "chat_id": {"type": "string", "description": "Optional chat id"},
                "broadcast": {"type": "boolean", "description": "Broadcast to subscribers"},
            },
            "required": [],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(url=url, headers={"Accept": "application/json"}, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=settings.SETTINGS.request_timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return json.loads(text)
    except Exception as err:  # noqa: BLE001
        raise UpstreamError(f"Market data API error: {err}") from err


def _base_url() -> str:
    return settings.SETTINGS.__dict__.get("market_data_base") or "https://api.binance.com"


def get_orderbook(
    symbol: str = "BTCUSDT",
    limit: int = 20,
    notify: bool = False,
    chat_id: Optional[str] = None,
    broadcast: bool = False,
) -> Dict[str, Any]:
    if not symbol:
        raise ValidationError("symbol is required")
    limit = max(5, min(int(limit or 20), 1000))
    url = f"{_base_url()}/api/v3/depth?symbol={symbol.upper()}&limit={limit}"
    data = _fetch_json(url)
    bids = data.get("bids", [])
    asks = data.get("asks", [])

    def _best(levels):
        if not levels:
            return None, None
        return float(levels[0][0]), float(levels[0][1])

    best_bid, best_bid_qty = _best(bids)
    best_ask, best_ask_qty = _best(asks)
    mid = None
    spread = None
    if best_bid and best_ask:
        mid = (best_bid + best_ask) / 2
        spread = best_ask - best_bid

    out = {
        "symbol": symbol.upper(),
        "bestBid": best_bid,
        "bestAsk": best_ask,
        "mid": mid,
        "spread": spread,
        "bids": bids,
        "asks": asks,
        "source": _base_url(),
    }

    if notify:
        msg = (
            f"Orderbook {symbol.upper()}\n"
            f"Bid: {best_bid} ({best_bid_qty})\n"
            f"Ask: {best_ask} ({best_ask_qty})\n"
            f"Spread: {spread}"
        )
        if broadcast:
            telegram_broadcast(msg)
        else:
            send_telegram(msg, chat_id=chat_id)

    return out


def get_kline(
    symbol: str = "BTCUSDT",
    interval: str = "1m",
    limit: int = 50,
    notify: bool = False,
    chat_id: Optional[str] = None,
    broadcast: bool = False,
) -> Dict[str, Any]:
    if not symbol:
        raise ValidationError("symbol is required")
    interval = interval or "1m"
    limit = max(1, min(int(limit or 50), 1000))
    url = f"{_base_url()}/api/v3/klines?symbol={symbol.upper()}&interval={interval}&limit={limit}"
    data = _fetch_json(url)

    candles = []
    for row in data:
        candles.append(
            {
                "openTime": row[0],
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
                "closeTime": row[6],
            }
        )

    out = {
        "symbol": symbol.upper(),
        "interval": interval,
        "count": len(candles),
        "candles": candles,
        "source": _base_url(),
    }

    if notify and candles:
        last = candles[-1]
        msg = (
            f"Kline {symbol.upper()} {interval}\n"
            f"O:{last['open']} H:{last['high']} L:{last['low']} C:{last['close']} V:{last['volume']}"
        )
        if broadcast:
            telegram_broadcast(msg)
        else:
            send_telegram(msg, chat_id=chat_id)

    return out


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "get_orderbook":
        return get_orderbook(
            symbol=args.get("symbol", "BTCUSDT"),
            limit=args.get("limit", 20),
            notify=bool(args.get("notify")),
            chat_id=args.get("chat_id"),
            broadcast=bool(args.get("broadcast")),
        )
    if name == "get_kline":
        return get_kline(
            symbol=args.get("symbol", "BTCUSDT"),
            interval=args.get("interval", "1m"),
            limit=args.get("limit", 50),
            notify=bool(args.get("notify")),
            chat_id=args.get("chat_id"),
            broadcast=bool(args.get("broadcast")),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="get_orderbook", description="Fetch orderbook snapshot (REST).")
    def tool_get_orderbook(
        symbol: str = "BTCUSDT",
        limit: int = 20,
        notify: bool = False,
        chat_id: str | None = None,
        broadcast: bool = False,
    ) -> dict:
        return safety.enrich(
            get_orderbook(symbol=symbol, limit=limit, notify=notify, chat_id=chat_id, broadcast=broadcast)
        )

    @mcp.tool(name="get_kline", description="Fetch kline data (REST).")
    def tool_get_kline(
        symbol: str = "BTCUSDT",
        interval: str = "1m",
        limit: int = 50,
        notify: bool = False,
        chat_id: str | None = None,
        broadcast: bool = False,
    ) -> dict:
        return safety.enrich(
            get_kline(symbol=symbol, interval=interval, limit=limit, notify=notify, chat_id=chat_id, broadcast=broadcast)
        )
