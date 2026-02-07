"""Funds flow module (Task 5): deposit/withdraw planning & chain selection."""

from __future__ import annotations

from typing import Any, Dict, List, Optional
import re

from tron_mcp import safety, settings
from tron_mcp.modules.chain_ops import chain_transfer_flow, chain_tx_status
from tron_mcp.modules.exchange_adapter import (
    exchange_fetch_withdrawals,
    exchange_get_deposit_address,
    exchange_withdraw,
)
from tron_mcp.utils.errors import ValidationError


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "prepare_deposit_withdraw",
        "description": "Prepare a deposit/withdraw plan with chain selection.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {"type": "string", "description": "deposit or withdraw"},
                "token": {"type": "string", "description": "TRX/USDT/etc"},
                "amount": {"type": "string"},
                "network": {"type": "string", "description": "TRON (default)"},
                "from_address": {"type": "string"},
                "to_address": {"type": "string"},
                "mode": {"type": "string", "description": "onchain or exchange"},
                "token_contract": {"type": "string"},
                "decimals": {"type": "integer"},
                "sign": {"type": "boolean"},
                "broadcast": {"type": "boolean"},
                "exchange_id": {"type": "string"},
                "api_key": {"type": "string"},
                "secret": {"type": "string"},
                "password": {"type": "string"},
                "api_domain": {"type": "string"},
                "proxy": {"type": "string"},
                "tag": {"type": "string"},
                "execute": {"type": "boolean"},
            },
            "required": ["action", "token"],
        },
    }
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}

TRON_B58_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")


def _infer_exchange_network(token: str, address: Optional[str], network: Optional[str]) -> Optional[str]:
    if network:
        return network
    if not address:
        return None
    if TRON_B58_RE.fullmatch(address):
        return "TRX" if token.upper() == "TRX" else "TRC20"
    return None


def _infer_standard(token: str, token_contract: Optional[str]) -> str:
    if token_contract:
        return "TRC20"
    token_upper = token.upper()
    if token_upper == "TRX":
        return "TRX"
    return "TRC20"


def prepare_deposit_withdraw(
    action: str,
    token: str,
    amount: Optional[str] = None,
    network: Optional[str] = None,
    from_address: Optional[str] = None,
    to_address: Optional[str] = None,
    mode: Optional[str] = None,
    token_contract: Optional[str] = None,
    decimals: Optional[int] = None,
    sign: bool = False,
    broadcast: bool = False,
    exchange_id: Optional[str] = None,
    api_key: Optional[str] = None,
    secret: Optional[str] = None,
    password: Optional[str] = None,
    api_domain: Optional[str] = None,
    proxy: Optional[str] = None,
    tag: Optional[str] = None,
    execute: bool = False,
) -> Dict[str, Any]:
    if not action or action.lower() not in {"deposit", "withdraw"}:
        raise ValidationError("action must be deposit or withdraw")
    if not token:
        raise ValidationError("token is required")

    action = action.lower()
    mode = (mode or "onchain").lower()
    network = (network or "TRON").upper()
    standard = _infer_standard(token, token_contract)

    plan: Dict[str, Any] = {
        "action": action,
        "token": token.upper(),
        "network": network,
        "standard": standard,
        "mode": mode,
        "notes": [],
        "steps": [],
    }

    if network != "TRON":
        plan["notes"].append("Only TRON network is supported in this module.")

    if mode == "exchange":
        inferred_network = _infer_exchange_network(token, to_address, network)
        if inferred_network and not network:
            plan["notes"].append(f"Inferred network: {inferred_network}")
        plan["steps"].extend(
            [
                "Call exchange API to request deposit/withdraw.",
                "Poll exchange withdrawal status.",
                "Monitor on-chain tx status after broadcast.",
            ]
        )
        if action == "deposit":
            plan["steps"].append("Fetch deposit address from exchange")
            if execute:
                plan["deposit_address"] = exchange_get_deposit_address(
                    exchange_id=exchange_id,
                    api_key=api_key,
                    secret=secret,
                    password=password,
                    api_domain=api_domain,
                    proxy=proxy,
                    sandbox=False,
                    currency=token.upper(),
                    network=inferred_network or network,
                )
            return plan

        if action == "withdraw":
            if not to_address or not amount:
                plan["notes"].append("Provide to_address and amount to execute withdrawal.")
                return plan
            if execute:
                plan["withdraw"] = exchange_withdraw(
                    exchange_id=exchange_id,
                    api_key=api_key,
                    secret=secret,
                    password=password,
                    api_domain=api_domain,
                    proxy=proxy,
                    sandbox=False,
                    currency=token.upper(),
                    amount=float(amount),
                    address=to_address,
                    tag=tag,
                    network=inferred_network or network,
                )
                plan["withdrawals"] = exchange_fetch_withdrawals(
                    exchange_id=exchange_id,
                    api_key=api_key,
                    secret=secret,
                    password=password,
                    api_domain=api_domain,
                    proxy=proxy,
                    sandbox=False,
                    currency=token.upper(),
                )
                txid = None
                if isinstance(plan["withdraw"], dict):
                    txid = plan["withdraw"].get("txid") or plan["withdraw"].get("id")
                if txid:
                    if (inferred_network or network) in {"TRX", "TRC20", "TRON"}:
                        plan["monitor"] = {"tool": "chain_tx_status", "txid": txid}
                        try:
                            plan["chain_status"] = chain_tx_status(txid)
                        except Exception:
                            pass
                    else:
                        plan["monitor"] = {"tool": "exchange_fetch_withdrawals", "currency": token.upper()}
                        plan["notes"].append("Non-TRON network: monitor via exchange or external explorer.")
            return plan

        plan["monitor"] = {"tool": "get_tx_status"}
        return plan

    # On-chain flow (non-custodial)
    if action == "withdraw" and from_address and to_address and amount:
        asset = "TRX" if standard == "TRX" else "TRC20"
        plan["steps"].append("Build unsigned transaction")
        plan["tx_flow"] = chain_transfer_flow(
            asset=asset,
            from_address=from_address,
            to_address=to_address,
            amount=amount,
            decimals=decimals or 6,
            token_contract=token_contract or settings.SETTINGS.usdt_contract,
            sign=sign,
            broadcast=broadcast,
        )
        if sign:
            plan["steps"].append("Sign with local key")
        if broadcast:
            plan["steps"].append("Broadcast signed tx")
        plan["monitor"] = {"tool": "get_tx_status"}
        return plan

    plan["steps"].append("Provide from_address/to_address/amount to build on-chain tx")
    plan["monitor"] = {"tool": "get_tx_status"}
    return plan


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "prepare_deposit_withdraw":
        return prepare_deposit_withdraw(
            action=args.get("action"),
            token=args.get("token"),
            amount=args.get("amount"),
            network=args.get("network"),
            from_address=args.get("from_address"),
            to_address=args.get("to_address"),
            mode=args.get("mode"),
            token_contract=args.get("token_contract"),
            decimals=args.get("decimals"),
            sign=bool(args.get("sign")),
            broadcast=bool(args.get("broadcast")),
            exchange_id=args.get("exchange_id"),
            api_key=args.get("api_key"),
            secret=args.get("secret"),
            password=args.get("password"),
            api_domain=args.get("api_domain"),
            proxy=args.get("proxy"),
            tag=args.get("tag"),
            execute=bool(args.get("execute")),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="prepare_deposit_withdraw", description="Prepare a deposit/withdraw plan with chain selection.")
    def tool_prepare_deposit_withdraw(
        action: str,
        token: str,
        amount: str | None = None,
        network: str | None = None,
        from_address: str | None = None,
        to_address: str | None = None,
        mode: str | None = None,
        token_contract: str | None = None,
        decimals: int | None = None,
        sign: bool = False,
        broadcast: bool = False,
        exchange_id: str | None = None,
        api_key: str | None = None,
        secret: str | None = None,
        password: str | None = None,
        api_domain: str | None = None,
        proxy: str | None = None,
        tag: str | None = None,
        execute: bool = False,
    ) -> dict:
        return safety.enrich(
            prepare_deposit_withdraw(
                action=action,
                token=token,
                amount=amount,
                network=network,
                from_address=from_address,
                to_address=to_address,
                mode=mode,
                token_contract=token_contract,
                decimals=decimals,
                sign=sign,
                broadcast=broadcast,
                exchange_id=exchange_id,
                api_key=api_key,
                secret=secret,
                password=password,
                api_domain=api_domain,
                proxy=proxy,
                tag=tag,
                execute=execute,
            )
        )
