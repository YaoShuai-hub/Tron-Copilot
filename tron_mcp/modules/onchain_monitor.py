"""On-chain asset monitor: detect balance changes and notify."""

from __future__ import annotations

import json
import time
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import re

from tron_mcp import safety, settings
from tron_mcp.tron_api import fetch_account, fetch_account_trongrid
from tron_mcp.utils.errors import ValidationError, UpstreamError
from tron_mcp.modules.audit_log import audit_log_event
from tron_mcp.modules.notify_telegram import send_telegram, telegram_broadcast


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "onchain_snapshot",
        "description": "Fetch TRON on-chain balances for configured addresses/tokens.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "addresses": {"type": "array", "items": {"type": "string"}},
                "tokens": {"type": "array", "items": {"type": "string"}},
                "rules_path": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "onchain_alerts",
        "description": "Compare on-chain balances with previous snapshot and alert by rules.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "addresses": {"type": "array", "items": {"type": "string"}},
                "tokens": {"type": "array", "items": {"type": "string"}},
                "rules_path": {"type": "string"},
                "state_path": {"type": "string"},
                "notify": {"type": "boolean"},
                "chat_id": {"type": "string"},
                "broadcast": {"type": "boolean"},
                "log_audit": {"type": "boolean"},
            },
            "required": [],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def _default_rules() -> Dict[str, Any]:
    return {
        "interval_sec": 60,
        "notify_on": ["increase", "decrease"],
        "min_change_default": 0.01,
        "addresses": [],
        "state_path": "logs/onchain_state.json",
        "evm_rpcs": {},
    }


def _rules_path(path: Optional[str]) -> Path:
    base = settings.SETTINGS.__dict__.get("onchain_rules_path") or "onchain_rules.json"
    return Path(path or base)


def _state_path(path: Optional[str]) -> Path:
    base = settings.SETTINGS.__dict__.get("onchain_state_path") or "logs/onchain_state.json"
    return Path(path or base)


def _merge_rules(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = _merge_rules(dict(base[key]), value)
        else:
            base[key] = value
    return base


def _load_rules(path: Optional[str]) -> Dict[str, Any]:
    rules = _default_rules()
    rules_path = _rules_path(path)
    if rules_path.exists():
        try:
            data = json.loads(rules_path.read_text())
            if isinstance(data, dict):
                rules = _merge_rules(rules, data)
        except Exception:
            pass
    rules = _apply_env_substitutions(rules)
    rules["rules_path"] = str(rules_path)
    return rules


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


_ENV_RE = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _apply_env_substitutions(value: Any) -> Any:
    env = _load_env_private(Path(".env.private"))

    if isinstance(value, dict):
        return {k: _apply_env_substitutions(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_apply_env_substitutions(v) for v in value]
    if isinstance(value, str):
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            return env.get(key, match.group(0))

        return _ENV_RE.sub(repl, value)
    return value


def _load_state(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def _save_state(path: Path, state: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2))


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


def _find_trc20_balance(account: Dict[str, Any], token: str) -> Tuple[str, float, int]:
    token_upper = token.upper()
    for row in _get_trc20_candidates(account):
        symbol = (_token_symbol(row) or "").upper()
        if symbol == token_upper or row.get("contract_address") == token or row.get("tokenId") == token:
            decimals = _token_decimals(row)
            raw = _token_balance_raw(row)
            value = float(raw) / (10 ** decimals) if raw else 0.0
            return raw, value, decimals
    return "0", 0.0, 6


def _fetch_trx_balance(address: str) -> float:
    acc = fetch_account_trongrid(address)
    return float(acc.get("balance", 0)) / 1_000_000


def _fetch_tron_token_balance(address: str, token: Dict[str, Any]) -> Dict[str, Any]:
    symbol = str(token.get("symbol") or "").upper()
    token_type = str(token.get("type") or "TRC20").upper()
    if symbol == "TRX" or token_type == "TRX":
        amount = _fetch_trx_balance(address)
        return {"token": "TRX", "raw": str(int(amount * 1_000_000)), "amount": amount, "decimals": 6}
    acc = fetch_account(address)
    raw, amount, decimals = _find_trc20_balance(acc, symbol or token.get("contract") or "")
    return {"token": symbol or "TRC20", "raw": raw, "amount": amount, "decimals": decimals}


def _fetch_evm_token_balance(address: str, token: Dict[str, Any], rpc_url: str) -> Dict[str, Any]:
    symbol = str(token.get("symbol") or "").upper()
    token_type = str(token.get("type") or "NATIVE").upper()
    if token_type == "NATIVE":
        amount = _evm_get_balance(address, rpc_url)
        return {"token": symbol or "NATIVE", "raw": str(int(amount * 10**18)), "amount": amount, "decimals": 18}
    contract = token.get("contract") or token.get("address")
    if not contract:
        raise ValidationError("ERC20 token requires contract")
    raw, amount, decimals = _evm_erc20_balance(address, contract, rpc_url, token.get("decimals"))
    return {"token": symbol or str(contract), "raw": raw, "amount": amount, "decimals": decimals}


def _normalize_targets(
    addresses: Optional[List[str]],
    tokens: Optional[List[str]],
    rules: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if addresses:
        return [{"address": addr, "tokens": tokens or ["TRX"], "chain": "TRON"} for addr in addresses]
    return list(rules.get("addresses") or [])


def _normalize_tokens(chain: str, tokens: List[Any]) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    chain_upper = chain.upper()
    for token in tokens:
        if isinstance(token, dict):
            entry = dict(token)
            entry.setdefault("symbol", str(entry.get("token") or entry.get("symbol") or "").upper())
            normalized.append(entry)
            continue
        token_str = str(token).strip()
        if not token_str:
            continue
        if chain_upper == "TRON":
            if token_str.upper() == "TRX":
                normalized.append({"symbol": "TRX", "type": "TRX"})
            else:
                normalized.append({"symbol": token_str.upper(), "type": "TRC20"})
        else:
            if token_str.lower().startswith("0x") and len(token_str) == 42:
                normalized.append({"symbol": token_str.upper(), "type": "ERC20", "contract": token_str})
            else:
                normalized.append({"symbol": token_str.upper(), "type": "NATIVE"})
    return normalized


def _evm_rpc_call(rpc_url: str, method: str, params: list[Any]) -> Any:
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url=rpc_url, data=data, headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=settings.SETTINGS.request_timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return json.loads(text)
    except Exception as err:  # noqa: BLE001
        raise UpstreamError(f"EVM RPC error: {err}") from err


def _evm_get_balance(address: str, rpc_url: str) -> float:
    if not address.startswith("0x"):
        address = "0x" + address
    data = _evm_rpc_call(rpc_url, "eth_getBalance", [address, "latest"])
    raw = data.get("result") or "0x0"
    return int(raw, 16) / 10**18


def _evm_erc20_decimals(contract: str, rpc_url: str) -> int:
    if not contract.startswith("0x"):
        contract = "0x" + contract
    payload = {"to": contract, "data": "0x313ce567"}  # decimals()
    data = _evm_rpc_call(rpc_url, "eth_call", [payload, "latest"])
    raw = data.get("result") or "0x0"
    return int(raw, 16)


def _evm_erc20_balance(address: str, contract: str, rpc_url: str, decimals: Optional[int]) -> Tuple[str, float, int]:
    if not address.startswith("0x"):
        address = "0x" + address
    if not contract.startswith("0x"):
        contract = "0x" + contract
    addr_hex = address[2:].rjust(64, "0")
    data = "0x70a08231" + addr_hex  # balanceOf(address)
    payload = {"to": contract, "data": data}
    res = _evm_rpc_call(rpc_url, "eth_call", [payload, "latest"])
    raw_hex = res.get("result") or "0x0"
    raw_int = int(raw_hex, 16)
    if decimals is None:
        try:
            decimals = _evm_erc20_decimals(contract, rpc_url)
        except Exception:
            decimals = 18
    amount = raw_int / (10**decimals)
    return str(raw_int), amount, int(decimals)


def onchain_snapshot(
    addresses: Optional[List[str]] = None,
    tokens: Optional[List[str]] = None,
    rules_path: Optional[str] = None,
) -> Dict[str, Any]:
    rules = _load_rules(rules_path)
    targets = _normalize_targets(addresses, tokens, rules)
    if not targets:
        return {"ok": False, "error": "no addresses configured", "rules": rules}

    snapshot: Dict[str, Any] = {"timestamp": int(time.time()), "items": []}
    for entry in targets:
        addr = entry.get("address")
        if not addr:
            continue
        chain = (entry.get("chain") or "TRON").upper()
        label = entry.get("label") or ""
        item = {"address": addr, "chain": chain, "label": label, "balances": [], "errors": []}
        token_entries = _normalize_tokens(chain, entry.get("tokens") or ["TRX"])
        if chain == "TRON":
            for token in token_entries:
                try:
                    item["balances"].append(_fetch_tron_token_balance(addr, token))
                except Exception as err:  # noqa: BLE001
                    item["errors"].append({"token": token.get("symbol"), "error": str(err)})
        else:
            rpc_url = entry.get("rpc_url")
            if not rpc_url:
                evm_rpcs = rules.get("evm_rpcs") or {}
                network = entry.get("network") or chain
                rpc_url = evm_rpcs.get(network) or evm_rpcs.get(str(network).lower())
            if not rpc_url:
                item["errors"].append({"token": "N/A", "error": "rpc_url missing for EVM chain"})
                snapshot["items"].append(item)
                continue
            for token in token_entries or [{"symbol": "NATIVE", "type": "NATIVE"}]:
                try:
                    item["balances"].append(_fetch_evm_token_balance(addr, token, rpc_url))
                except Exception as err:  # noqa: BLE001
                    item["errors"].append({"token": token.get("symbol"), "error": str(err)})
        snapshot["items"].append(item)

    if not snapshot["items"]:
        return {"ok": False, "error": "no valid addresses configured", "rules": rules}
    return {"ok": True, "snapshot": snapshot, "rules": rules}


def onchain_alerts(
    addresses: Optional[List[str]] = None,
    tokens: Optional[List[str]] = None,
    rules_path: Optional[str] = None,
    state_path: Optional[str] = None,
    notify: bool = False,
    chat_id: Optional[str] = None,
    broadcast: bool = False,
    log_audit: bool = True,
) -> Dict[str, Any]:
    rules = _load_rules(rules_path)
    snapshot_result = onchain_snapshot(addresses=addresses, tokens=tokens, rules_path=rules_path)
    if not snapshot_result.get("ok"):
        return snapshot_result

    state_file = _state_path(state_path or rules.get("state_path"))
    prev_state = _load_state(state_file)
    current = snapshot_result["snapshot"]
    alerts: List[Dict[str, Any]] = []

    notify_on = set(rules.get("notify_on") or ["increase", "decrease"])
    min_change_default = float(rules.get("min_change_default") or 0.0)
    alert_on_first = bool(rules.get("alert_on_first") or False)

    for item in current.get("items", []):
        addr = item.get("address")
        chain = item.get("chain") or "TRON"
        label = item.get("label") or ""
        key = f"{chain}:{addr}"
        prev_addr = (prev_state.get("balances") or {}).get(key, {})
        thresholds = {}
        entry_notify = None
        for entry in rules.get("addresses") or []:
            if entry.get("address") == addr:
                thresholds = entry.get("thresholds") or {}
                entry_notify = entry.get("notify")
                break
        for bal in item.get("balances", []):
            token = bal.get("token")
            current_amount = float(bal.get("amount") or 0.0)
            if not alert_on_first and token not in prev_addr:
                continue
            prev_amount = float(prev_addr.get(token, 0.0))
            change = current_amount - prev_amount
            threshold = float(thresholds.get(token, min_change_default))
            if abs(change) < threshold:
                continue
            direction = "increase" if change > 0 else "decrease"
            if direction not in notify_on:
                continue
            alerts.append(
                {
                    "label": label,
                    "chain": chain,
                    "address": addr,
                    "token": token,
                    "prev": prev_amount,
                    "current": current_amount,
                    "change": change,
                    "direction": direction,
                    "threshold": threshold,
                    "notify": entry_notify or {},
                }
            )

    # update state
    new_state = {"updated": int(time.time()), "balances": {}}
    for item in current.get("items", []):
        addr = item.get("address")
        chain = item.get("chain") or "TRON"
        key = f"{chain}:{addr}"
        new_state["balances"][key] = {b.get("token"): b.get("amount") for b in item.get("balances", [])}
    _save_state(state_file, new_state)

    if alerts and log_audit:
        try:
            audit_log_event(
                {
                    "action": "onchain_alerts",
                    "alerts": alerts,
                    "snapshot_ts": current.get("timestamp"),
                    "rules_path": rules.get("rules_path"),
                }
            )
        except Exception:
            pass

    if notify:
        # per-entry notification overrides (grouped by label + target)
        targeted_map: Dict[Tuple[str | None, bool], List[Dict[str, Any]]] = {}
        for alert in alerts:
            notify_cfg = alert.get("notify") or {}
            if not notify_cfg:
                continue
            target_chat = notify_cfg.get("chat_id") or chat_id
            target_broadcast = bool(notify_cfg.get("broadcast"))
            key = (target_chat, target_broadcast)
            targeted_map.setdefault(key, []).append(alert)

        for (target_chat, target_broadcast), group in targeted_map.items():
            title = "On-chain Alerts"
            if group and group[0].get("label"):
                title = f"On-chain Alerts [{group[0].get('label')}]"
            lines = [title]
            for alert in group[:8]:
                lines.append(
                    f"- {alert['chain']} {alert['address']} {alert['token']} {alert['direction']} "
                    f"{alert['change']:.6f} (now {alert['current']:.6f})"
                )
            msg = "\n".join(lines)
            if target_broadcast:
                res = telegram_broadcast(msg)
                if not res.get("ok"):
                    send_telegram(msg, chat_id=target_chat)
            else:
                send_telegram(msg, chat_id=target_chat)

        # global notification for alerts without per-entry notify config
        global_alerts = [a for a in alerts if not (a.get("notify") or {})]
        if global_alerts:
            lines = ["On-chain Alerts"]
            for alert in global_alerts[:8]:
                label = f"[{alert.get('label')}] " if alert.get("label") else ""
                lines.append(
                    f"- {label}{alert['chain']} {alert['address']} {alert['token']} {alert['direction']} "
                    f"{alert['change']:.6f} (now {alert['current']:.6f})"
                )
            msg = "\n".join(lines)
            if broadcast:
                res = telegram_broadcast(msg)
                if not res.get("ok"):
                    send_telegram(msg, chat_id=chat_id)
            else:
                send_telegram(msg, chat_id=chat_id)
        # no alerts -> no message

    return {"ok": True, "alerts": alerts, "snapshot": current, "rules": rules, "statePath": str(state_file)}


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "onchain_snapshot":
        return onchain_snapshot(
            addresses=args.get("addresses"),
            tokens=args.get("tokens"),
            rules_path=args.get("rules_path"),
        )
    if name == "onchain_alerts":
        return onchain_alerts(
            addresses=args.get("addresses"),
            tokens=args.get("tokens"),
            rules_path=args.get("rules_path"),
            state_path=args.get("state_path"),
            notify=bool(args.get("notify")),
            chat_id=args.get("chat_id"),
            broadcast=bool(args.get("broadcast")),
            log_audit=bool(args.get("log_audit", True)),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="onchain_snapshot", description="Fetch TRON on-chain balances for configured addresses/tokens.")
    def tool_onchain_snapshot(
        addresses: List[str] | None = None,
        tokens: List[str] | None = None,
        rules_path: str | None = None,
    ) -> dict:
        return safety.enrich(
            onchain_snapshot(addresses=addresses, tokens=tokens, rules_path=rules_path)
        )

    @mcp.tool(name="onchain_alerts", description="Compare on-chain balances and alert by rules.")
    def tool_onchain_alerts(
        addresses: List[str] | None = None,
        tokens: List[str] | None = None,
        rules_path: str | None = None,
        state_path: str | None = None,
        notify: bool = False,
        chat_id: str | None = None,
        broadcast: bool = False,
        log_audit: bool = True,
    ) -> dict:
        return safety.enrich(
            onchain_alerts(
                addresses=addresses,
                tokens=tokens,
                rules_path=rules_path,
                state_path=state_path,
                notify=notify,
                chat_id=chat_id,
                broadcast=broadcast,
                log_audit=log_audit,
            )
        )
