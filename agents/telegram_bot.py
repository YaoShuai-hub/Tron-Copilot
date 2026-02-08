"""Telegram bot runner: chat with the local assistant via long polling."""

from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

from tron_mcp import settings, tools
from tron_mcp.ai import call_chat
from tron_mcp.utils.errors import UpstreamError, ValidationError
from tron_mcp.modules import notify_telegram


log = logging.getLogger("telegram_bot")


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


def _get_bot_token() -> str:
    token = settings.SETTINGS.telegram_bot_token
    if not token:
        env = _load_env_private(Path(".env.private"))
        token = env.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise ValidationError("TELEGRAM_BOT_TOKEN not found in settings or .env.private")
    return token


def _get_auth_bot_token() -> Optional[str]:
    env = _load_env_private(Path(".env.private"))
    return env.get("TELEGRAM_AUTH_BOT_TOKEN")


def _get_allowed_chats() -> Optional[set[str]]:
    env = _load_env_private(Path(".env.private"))
    allow_all = env.get("TELEGRAM_ALLOW_ALL") or ""
    if allow_all.strip().lower() in {"1", "true", "yes", "on"}:
        return None

    chat_id = settings.SETTINGS.telegram_chat_id or env.get("TELEGRAM_CHAT_ID")
    items = notify_telegram._load_subscribers()  # type: ignore[attr-defined]
    if items:
        return {str(item.get("chat_id")) for item in items if item.get("chat_id")}
    if chat_id:
        return {str(chat_id)}
    return set()


def _telegram_api_get(
    token: str,
    method: str,
    params: Dict[str, Any],
    timeout_sec: Optional[float] = None,
) -> Dict[str, Any]:
    query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
    url = f"https://api.telegram.org/bot{token}/{method}?{query}"
    req = urllib.request.Request(url=url, method="GET")
    try:
        timeout = timeout_sec if timeout_sec is not None else settings.SETTINGS.request_timeout
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return json.loads(text)
    except Exception as err:  # noqa: BLE001
        raise UpstreamError(f"Telegram API error: {err}") from err


def _trim_message(text: str, limit: int = 3500) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + "...(truncated)"


def _exec_tool_call(name: str, arguments_json: str) -> Dict[str, Any]:
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as err:
        return {"error": f"Invalid arguments JSON: {err}", "raw": arguments_json}
    try:
        return tools.call_tool(name, args)
    except Exception as err:  # noqa: BLE001
        return {"error": f"Tool execution failed: {err}"}


def _needs_verification(name: str, args: Dict[str, Any]) -> bool:
    if name == "transfer_trx_local_sign_broadcast":
        return True
    if name == "chain_transfer_flow" and (args.get("sign") or args.get("broadcast")):
        return True
    return False


def _build_unsigned_preview(name: str, args: Dict[str, Any]) -> Dict[str, Any] | None:
    try:
        if name == "transfer_trx_local_sign_broadcast":
            return tools.call_tool(
                "create_unsigned_trx_transfer",
                {
                    "from_address": args.get("from_address"),
                    "to_address": args.get("to_address"),
                    "amount_trx": args.get("amount_trx"),
                    "amount_sun": args.get("amount_sun"),
                },
            )
        if name == "chain_transfer_flow":
            preview_args = dict(args or {})
            preview_args["sign"] = False
            preview_args["broadcast"] = False
            return tools.call_tool("chain_transfer_flow", preview_args)
    except Exception:
        return None
    return None


def _generate_verification_code() -> str:
    return str(int(time.time() * 1000) % 1_000_000).zfill(6)


def _agent_loop(
    user_text: str,
    messages: Optional[List[Dict[str, Any]]] = None,
    max_rounds: int = 12,
    chat_id: Optional[str] = None,
    pending_verifications: Optional[Dict[str, Dict[str, Any]]] = None,
    auth_bot_token: Optional[str] = None,
) -> Dict[str, Any]:
    tool_schema = tools.list_tools()["tools"]
    history: List[Dict[str, Any]] = list(messages or [])
    history.append({"role": "user", "content": user_text})

    for _ in range(max_rounds):
        resp = call_chat(history, tools_schema=tool_schema)
        choice = resp.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls") or []

        if not tool_calls:
            history.append(message)
            return {"final": message, "messages": history}

        history.append(
            {
                "role": "assistant",
                "content": message.get("content", ""),
                "tool_calls": tool_calls,
            }
        )
        for call in tool_calls:
            name = call.get("function", {}).get("name")
            arguments = call.get("function", {}).get("arguments", "{}")
            args_obj = {}
            try:
                args_obj = json.loads(arguments or "{}")
            except json.JSONDecodeError:
                args_obj = {}

            if chat_id and pending_verifications is not None and _needs_verification(name, args_obj):
                code = _generate_verification_code()
                preview = _build_unsigned_preview(name, args_obj)
                pending_verifications[chat_id] = {
                    "code": code,
                    "expires_at": time.time() + 300,
                    "tool_name": name,
                    "tool_args": args_obj,
                    "preview": preview,
                }
                note = "需要验证码确认交易。\n"
                if preview:
                    note += f"交易预览: {json.dumps(preview, ensure_ascii=False)[:1200]}\n"
                note += f"验证码: {code}\n请回复验证码以继续签名并广播。"
                try:
                    notify_telegram.send_telegram(
                        message=_trim_message(note),
                        chat_id=chat_id,
                        token=auth_bot_token,
                    )
                except Exception as err:  # noqa: BLE001
                    log.warning("Auth bot send failed, fallback to main bot: %s", err)
                    notify_telegram.send_telegram(message=_trim_message(note), chat_id=chat_id)
                # Always notify in main bot that a code was sent
                notify_telegram.send_telegram(
                    message="已发送验证码到验证 bot，请查看并回复验证码。",
                    chat_id=chat_id,
                )
                result = {"status": "VERIFICATION_REQUIRED", "message": "OTP sent to Telegram."}
            else:
                result = _exec_tool_call(name, arguments)
            history.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

    return {
        "final": {"role": "assistant", "content": "Stopped after safety cap."},
        "messages": history,
    }


def run_telegram_bot(poll_timeout: int = 20, max_rounds: int = 12) -> None:
    token = _get_bot_token()
    auth_bot_token = _get_auth_bot_token()
    allowed_chats = _get_allowed_chats()
    offset = 0
    conversations: Dict[str, List[Dict[str, Any]]] = {}
    pending_verifications: Dict[str, Dict[str, Any]] = {}

    log.info("Telegram bot started. Poll timeout=%s", poll_timeout)
    while True:
        request_timeout = max(float(settings.SETTINGS.request_timeout), poll_timeout + 5)
        try:
            data = _telegram_api_get(
                token,
                "getUpdates",
                {"timeout": poll_timeout, "offset": offset},
                timeout_sec=request_timeout,
            )
        except UpstreamError as err:
            log.warning("Telegram polling error: %s", err)
            time.sleep(1.0)
            continue
        if not data.get("ok"):
            time.sleep(1.0)
            continue
        updates = data.get("result") or []
        for upd in updates:
            offset = max(offset, int(upd.get("update_id", 0)) + 1)
            msg = upd.get("message") or upd.get("edited_message")
            if not msg:
                continue
            text = (msg.get("text") or "").strip()
            if not text:
                continue
            chat_id = str((msg.get("chat") or {}).get("id"))
            if not chat_id:
                continue

            if text in {"/start", "/help"}:
                notify_telegram.send_telegram(
                    message="已连接到本地助手。直接发送问题即可。\n"
                    "支持 /reset 清空上下文。\n"
                    "如需订阅通知，请运行 telegram_subscribe。",
                    chat_id=chat_id,
                )
                continue
            if text == "/reset":
                conversations.pop(chat_id, None)
                pending_verifications.pop(chat_id, None)
                notify_telegram.send_telegram(message="上下文已清空。", chat_id=chat_id)
                continue

            if allowed_chats is not None and chat_id not in allowed_chats:
                notify_telegram.send_telegram(
                    message="该 chat_id 未授权。请配置 TELEGRAM_CHAT_ID 或订阅列表。",
                    chat_id=chat_id,
                )
                continue

            pending = pending_verifications.get(chat_id)
            if pending:
                expires_at = pending.get("expires_at", 0)
                if time.time() > expires_at:
                    pending_verifications.pop(chat_id, None)
                    notify_telegram.send_telegram(message="验证码已过期，请重新发起交易。", chat_id=chat_id)
                    continue
                if text.strip() != pending.get("code"):
                    pending_verifications.pop(chat_id, None)
                    notify_telegram.send_telegram(
                        message="验证码错误，本次交易已取消。如需继续请重新发起。",
                        chat_id=chat_id,
                    )
                    continue

                try:
                    result = _exec_tool_call(pending.get("tool_name"), json.dumps(pending.get("tool_args", {})))
                    pending_verifications.pop(chat_id, None)
                    reply = json.dumps(result, ensure_ascii=False)
                except Exception as err:  # noqa: BLE001
                    reply = f"执行失败: {err}"
                notify_telegram.send_telegram(message=_trim_message(reply), chat_id=chat_id)
                continue

            try:
                result = _agent_loop(
                    text,
                    messages=conversations.get(chat_id),
                    max_rounds=max_rounds,
                    chat_id=chat_id,
                    pending_verifications=pending_verifications,
                    auth_bot_token=auth_bot_token,
                )
                conversations[chat_id] = result.get("messages", [])
                reply = result.get("final", {}).get("content", "") or "(empty reply)"
            except (UpstreamError, ValidationError, Exception) as err:
                reply = f"LLM error: {err}"

            notify_telegram.send_telegram(message=_trim_message(reply), chat_id=chat_id)


def main() -> int:
    logging.basicConfig(level="INFO")
    run_telegram_bot()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
