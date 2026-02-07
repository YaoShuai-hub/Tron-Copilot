"""Chain operations module (Task 4): build/sign/broadcast/tx-status."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from tron_mcp import safety
from tron_mcp.extensions import tx_assistant, trc20_assistant, local_signer
from tron_mcp.tron_api import broadcast_transaction, fetch_tx_info, fetch_tx_meta
from tron_mcp.utils.errors import ValidationError
from tron_mcp.utils.validation import validate_txid
from tron_mcp.utils.encoding import tron_hex_to_b58


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "chain_transfer_flow",
        "description": "Build (and optionally sign/broadcast) a TRX/TRC20 transfer.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "asset": {"type": "string", "description": "TRX or TRC20"},
                "from_address": {"type": "string"},
                "to_address": {"type": "string"},
                "amount": {"type": "string", "description": "Human amount"},
                "amount_raw": {"type": "string", "description": "Raw integer amount"},
                "decimals": {"type": "integer"},
                "token_contract": {"type": "string"},
                "fee_limit": {"type": "integer"},
                "sign": {"type": "boolean", "description": "Sign locally using .env.private"},
                "broadcast": {"type": "boolean", "description": "Broadcast signed tx"},
                "env_path": {"type": "string", "description": "Path to .env.private"},
            },
            "required": ["asset", "from_address", "to_address"],
        },
    },
    {
        "name": "chain_tx_status",
        "description": "Check transaction status with parsed from/to (TRONGRID).",
        "inputSchema": {
            "type": "object",
            "properties": {"txid": {"type": "string"}},
            "required": ["txid"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


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


def _extract_owner_to_from_raw(tx: Dict[str, Any]) -> tuple[str | None, str | None, Any]:
    raw = tx.get("raw_data") or {}
    contract = (raw.get("contract") or [{}])[0] or {}
    value = (contract.get("parameter") or {}).get("value") or {}
    owner = value.get("owner_address") or value.get("ownerAddress")
    to = value.get("to_address") or value.get("toAddress")
    amount = value.get("amount")
    return owner, to, amount


def chain_tx_status(txid: str) -> Dict[str, Any]:
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
        raw_owner, raw_to, raw_amount = _extract_owner_to_from_raw(meta)
        owner = _normalize_address(raw_owner)
        to = _normalize_address(raw_to)
        amount = raw_amount

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


def chain_transfer_flow(
    asset: str,
    from_address: str,
    to_address: str,
    amount: Optional[str] = None,
    amount_raw: Optional[str] = None,
    decimals: Optional[int] = None,
    token_contract: Optional[str] = None,
    fee_limit: Optional[int] = None,
    sign: bool = False,
    broadcast: bool = False,
    env_path: Optional[str] = None,
) -> Dict[str, Any]:
    asset_upper = (asset or "").upper()
    if asset_upper not in {"TRX", "TRC20"}:
        raise ValidationError("asset must be TRX or TRC20")

    if asset_upper == "TRX":
        unsigned = tx_assistant.create_unsigned_trx_transfer(
            from_address=from_address,
            to_address=to_address,
            amount_trx=amount,
        )
    else:
        unsigned = trc20_assistant.create_unsigned_trc20_transfer(
            from_address=from_address,
            to_address=to_address,
            token_contract=token_contract,
            amount=amount,
            amount_raw=amount_raw,
            decimals=decimals,
            fee_limit=fee_limit,
        )

    out: Dict[str, Any] = {
        "unsigned": unsigned,
        "signed": None,
        "broadcast": None,
    }

    if sign:
        signed = local_signer.sign_transaction(unsigned.get("unsignedTx"))
        out["signed"] = signed
        if broadcast:
            out["broadcast"] = broadcast_transaction(signed["signed_tx"])
    elif broadcast:
        raise ValidationError("broadcast requires sign=true")

    # Audit log (best-effort)
    try:
        from tron_mcp.modules.audit_log import audit_log_event

        audit_log_event(
            {
                "action": "chain_transfer_flow",
                "asset": asset_upper,
                "from": from_address,
                "to": to_address,
                "amount": amount,
                "amount_raw": amount_raw,
                "unsigned_txid": unsigned.get("txid"),
                "signed_txid": (out.get("signed") or {}).get("txid"),
                "broadcast": out.get("broadcast"),
            }
        )
    except Exception:
        pass

    return out


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "chain_transfer_flow":
        return chain_transfer_flow(
            asset=args.get("asset"),
            from_address=args.get("from_address"),
            to_address=args.get("to_address"),
            amount=args.get("amount"),
            amount_raw=args.get("amount_raw"),
            decimals=args.get("decimals"),
            token_contract=args.get("token_contract"),
            fee_limit=args.get("fee_limit"),
            sign=bool(args.get("sign")),
            broadcast=bool(args.get("broadcast")),
            env_path=args.get("env_path"),
        )
    if name == "chain_tx_status":
        return chain_tx_status(args.get("txid"))
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="chain_transfer_flow", description="Build (and optionally sign/broadcast) a TRX/TRC20 transfer.")
    def tool_chain_transfer_flow(
        asset: str,
        from_address: str,
        to_address: str,
        amount: str | None = None,
        amount_raw: str | None = None,
        decimals: int | None = None,
        token_contract: str | None = None,
        fee_limit: int | None = None,
        sign: bool = False,
        broadcast: bool = False,
        env_path: str | None = None,
    ) -> dict:
        return safety.enrich(
            chain_transfer_flow(
                asset=asset,
                from_address=from_address,
                to_address=to_address,
                amount=amount,
                amount_raw=amount_raw,
                decimals=decimals,
                token_contract=token_contract,
                fee_limit=fee_limit,
                sign=sign,
                broadcast=broadcast,
                env_path=env_path,
            )
        )

    @mcp.tool(name="chain_tx_status", description="Check transaction status with parsed from/to (TRONGRID).")
    def tool_chain_tx_status(txid: str) -> dict:
        return safety.enrich(chain_tx_status(txid))
