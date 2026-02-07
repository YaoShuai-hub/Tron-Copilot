"""Telegram notification module (Task 11)."""

from __future__ import annotations

import json
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from tron_mcp import safety, settings
from tron_mcp.utils.errors import ValidationError, UpstreamError


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "send_telegram",
        "description": "Send a Telegram message via bot token/chat id.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "token": {"type": "string"},
                "chat_id": {"type": "string"},
                "parse_mode": {"type": "string", "description": "Markdown or HTML"},
            },
            "required": ["message"],
        },
    }
    ,
    {
        "name": "telegram_subscribe",
        "description": "Subscribe a chat_id for notifications.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string"},
                "label": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "telegram_unsubscribe",
        "description": "Unsubscribe a chat_id from notifications.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "chat_id": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "telegram_list_subscribers",
        "description": "List all Telegram subscribers.",
        "inputSchema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "telegram_broadcast",
        "description": "Broadcast a message to all subscribers.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "parse_mode": {"type": "string", "description": "Markdown or HTML"},
                "token": {"type": "string"},
            },
            "required": ["message"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def _post_json(url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=settings.SETTINGS.request_timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return json.loads(text)
    except Exception as err:  # noqa: BLE001
        raise UpstreamError(f"Telegram API error: {err}") from err


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


def _subscribers_path() -> Path:
    return Path(settings.SETTINGS.telegram_subscribers_path or "logs/telegram_subscribers.json")


def _load_subscribers() -> List[Dict[str, Any]]:
    path = _subscribers_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_subscribers(items: List[Dict[str, Any]]) -> None:
    path = _subscribers_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(items, ensure_ascii=False, indent=2))


def send_telegram(message: str, token: Optional[str] = None, chat_id: Optional[str] = None, parse_mode: Optional[str] = None) -> Dict[str, Any]:
    if not message:
        raise ValidationError("message is required")
    token = token or settings.SETTINGS.__dict__.get("telegram_bot_token") or None
    chat_id = chat_id or settings.SETTINGS.__dict__.get("telegram_chat_id") or None
    if not token or not chat_id:
        env = _load_env_private(Path(".env.private"))
        token = token or env.get("TELEGRAM_BOT_TOKEN")
        chat_id = chat_id or env.get("TELEGRAM_CHAT_ID")
    if not token:
        raise ValidationError("token is required (or set TELEGRAM_BOT_TOKEN)")
    if not chat_id:
        raise ValidationError("chat_id is required (or set TELEGRAM_CHAT_ID)")

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    return _post_json(url, payload)


def telegram_subscribe(chat_id: Optional[str] = None, label: Optional[str] = None) -> Dict[str, Any]:
    if not chat_id:
        env = _load_env_private(Path(".env.private"))
        chat_id = env.get("TELEGRAM_CHAT_ID") or settings.SETTINGS.telegram_chat_id
    if not chat_id:
        raise ValidationError("chat_id is required")
    items = _load_subscribers()
    if not any(i.get("chat_id") == chat_id for i in items):
        items.append({"chat_id": str(chat_id), "label": label or ""})
        _save_subscribers(items)
    return {"ok": True, "count": len(items), "items": items}


def telegram_unsubscribe(chat_id: Optional[str] = None) -> Dict[str, Any]:
    if not chat_id:
        env = _load_env_private(Path(".env.private"))
        chat_id = env.get("TELEGRAM_CHAT_ID") or settings.SETTINGS.telegram_chat_id
    if not chat_id:
        raise ValidationError("chat_id is required")
    items = [i for i in _load_subscribers() if i.get("chat_id") != str(chat_id)]
    _save_subscribers(items)
    return {"ok": True, "count": len(items), "items": items}


def telegram_list_subscribers() -> Dict[str, Any]:
    items = _load_subscribers()
    return {"ok": True, "count": len(items), "items": items}


def telegram_broadcast(message: str, parse_mode: Optional[str] = None, token: Optional[str] = None) -> Dict[str, Any]:
    if not message:
        raise ValidationError("message is required")
    items = _load_subscribers()
    if not items:
        return {"ok": False, "error": "no subscribers"}
    token = token or settings.SETTINGS.telegram_bot_token
    if not token:
        env = _load_env_private(Path(".env.private"))
        token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValidationError("token is required (or set TELEGRAM_BOT_TOKEN)")
    results = []
    for item in items:
        chat_id = item.get("chat_id")
        if not chat_id:
            continue
        results.append(send_telegram(message=message, token=token, chat_id=chat_id, parse_mode=parse_mode))
    return {"ok": True, "count": len(results), "results": results}


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "send_telegram":
        return send_telegram(
            message=args.get("message"),
            token=args.get("token"),
            chat_id=args.get("chat_id"),
            parse_mode=args.get("parse_mode"),
        )
    if name == "telegram_subscribe":
        return telegram_subscribe(chat_id=args.get("chat_id"), label=args.get("label"))
    if name == "telegram_unsubscribe":
        return telegram_unsubscribe(chat_id=args.get("chat_id"))
    if name == "telegram_list_subscribers":
        return telegram_list_subscribers()
    if name == "telegram_broadcast":
        return telegram_broadcast(
            message=args.get("message"),
            parse_mode=args.get("parse_mode"),
            token=args.get("token"),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="send_telegram", description="Send a Telegram message via bot token/chat id.")
    def tool_send_telegram(message: str, token: str | None = None, chat_id: str | None = None, parse_mode: str | None = None) -> dict:
        return safety.enrich(send_telegram(message=message, token=token, chat_id=chat_id, parse_mode=parse_mode))

    @mcp.tool(name="telegram_subscribe", description="Subscribe a chat_id for notifications.")
    def tool_telegram_subscribe(chat_id: str | None = None, label: str | None = None) -> dict:
        return safety.enrich(telegram_subscribe(chat_id=chat_id, label=label))

    @mcp.tool(name="telegram_unsubscribe", description="Unsubscribe a chat_id from notifications.")
    def tool_telegram_unsubscribe(chat_id: str | None = None) -> dict:
        return safety.enrich(telegram_unsubscribe(chat_id=chat_id))

    @mcp.tool(name="telegram_list_subscribers", description="List all Telegram subscribers.")
    def tool_telegram_list_subscribers() -> dict:
        return safety.enrich(telegram_list_subscribers())

    @mcp.tool(name="telegram_broadcast", description="Broadcast a message to all subscribers.")
    def tool_telegram_broadcast(message: str, parse_mode: str | None = None, token: str | None = None) -> dict:
        return safety.enrich(telegram_broadcast(message=message, parse_mode=parse_mode, token=token))
