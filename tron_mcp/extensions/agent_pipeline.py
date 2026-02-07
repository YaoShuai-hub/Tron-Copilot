"""Agent pipeline: intent -> confirmation -> build -> sign request -> broadcast."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from tron_mcp import safety
from . import tx_assistant, trc20_assistant, local_signer
from tron_mcp.tron_api import fetch_chain_parameters
from tron_mcp.utils.errors import ValidationError
from tron_mcp.utils.validation import validate_address
from tron_mcp.tron_api import broadcast_transaction


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "agent_parse_intent",
        "description": "Heuristic NLP parse of transfer intent (from/to/amount/asset).",
        "inputSchema": {
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
        },
    },
    {
        "name": "agent_prepare_transaction",
        "description": "Parse prompt and build unsigned tx + confirmation summary (no signing).",
        "inputSchema": {
            "type": "object",
            "properties": {"prompt": {"type": "string"}},
            "required": ["prompt"],
        },
    },
    {
        "name": "agent_request_signature",
        "description": "Wrap unsigned tx as a signing request; does not sign or store keys.",
        "inputSchema": {
            "type": "object",
            "properties": {"unsigned_tx": {"type": "object"}},
            "required": ["unsigned_tx"],
        },
    },
    {
        "name": "broadcast_signed_transaction",
        "description": "Broadcast a signed transaction to TRON via TRONGRID.",
        "inputSchema": {
            "type": "object",
            "properties": {"signed_tx": {"type": "object"}},
            "required": ["signed_tx"],
        },
    },
    {
        "name": "prepare_trx_transfer_flow",
        "description": "Build unsigned TRX transfer and return a signing request (no sign/broadcast).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_address": {"type": "string", "description": "Sender TRON Base58 address"},
                "to_address": {"type": "string", "description": "Recipient TRON Base58 address"},
                "amount_trx": {"type": "string", "description": "Amount in TRX (e.g., '1.25')"},
                "amount_sun": {"type": "integer", "description": "Amount in sun (1 TRX = 1,000,000 sun)"},
            },
            "required": ["from_address", "to_address"],
        },
    },
    {
        "name": "transfer_trx_local_sign_broadcast",
        "description": "Create, sign locally, and broadcast a TRX transfer using .env.private.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_address": {"type": "string", "description": "Sender TRON Base58 address"},
                "to_address": {"type": "string", "description": "Recipient TRON Base58 address"},
                "amount_trx": {"type": "string", "description": "Amount in TRX (e.g., '1.25')"},
                "amount_sun": {"type": "integer", "description": "Amount in sun (1 TRX = 1,000,000 sun)"},
                "env_path": {"type": "string", "description": "Path to env file (default .env.private)"},
            },
            "required": ["from_address", "to_address"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}

_ADDR_RE = re.compile(r"T[1-9A-HJ-NP-Za-km-z]{33}")
_AMOUNT_RE = re.compile(r"\b([0-9]+(?:\.[0-9]+)?)\b")


def _extract_addresses(prompt: str) -> List[str]:
    return _ADDR_RE.findall(prompt or "")


def _extract_from_to(prompt: str) -> tuple[Optional[str], Optional[str]]:
    if not prompt:
        return None, None
    from_match = re.search(r"from\\s+(T[1-9A-HJ-NP-Za-km-z]{33})", prompt, re.IGNORECASE)
    to_match = re.search(r"to\\s+(T[1-9A-HJ-NP-Za-km-z]{33})", prompt, re.IGNORECASE)
    from_addr = from_match.group(1) if from_match else None
    to_addr = to_match.group(1) if to_match else None
    if from_addr or to_addr:
        return from_addr, to_addr
    addrs = _extract_addresses(prompt)
    return (addrs[0] if len(addrs) >= 1 else None, addrs[1] if len(addrs) >= 2 else None)


def _extract_amount(prompt: str) -> Optional[str]:
    if not prompt:
        return None
    cleaned = _ADDR_RE.sub(" ", prompt)
    m = _AMOUNT_RE.search(cleaned)
    return m.group(1) if m else None


def parse_intent(prompt: str) -> Dict[str, Any]:
    if not prompt:
        raise ValidationError("prompt is required")
    p = prompt.lower()
    from_addr, to_addr = _extract_from_to(prompt)
    amount = _extract_amount(prompt)

    asset = "TRX"
    if "usdt" in p or "trc20" in p:
        asset = "TRC20"

    action = "TRANSFER"
    if "vote" in p:
        action = "VOTE"
    elif "delegate" in p or "stake" in p or "freeze" in p:
        action = "RESOURCE"
    elif "contract" in p or "call" in p:
        action = "CONTRACT_CALL"

    confidence = 0.6 if (from_addr or to_addr) else 0.3
    if asset == "TRC20":
        confidence += 0.1
    if amount:
        confidence += 0.1

    return {
        "action": action,
        "asset": asset,
        "from": from_addr,
        "to": to_addr,
        "amount": amount,
        "confidence": round(min(confidence, 0.95), 2),
        "notes": "Heuristic parser. Provide from/to addresses and amount for best results.",
    }


def _confirmation_summary(intent: Dict[str, Any]) -> Dict[str, Any]:
    params = fetch_chain_parameters()
    table = {item.get("key"): item.get("value") for item in params.get("chainParameter", [])}
    return {
        "action": intent.get("action"),
        "asset": intent.get("asset"),
        "from": intent.get("from"),
        "to": intent.get("to"),
        "amount": intent.get("amount"),
        "feeBaseline": {
            "energyFeeSun": table.get("getEnergyFee"),
            "bandwidthFeeSun": table.get("getTransactionFee"),
            "createAccountFeeSun": table.get("getCreateAccountFee"),
            "memoFeePerByteSun": table.get("getMemoFee"),
        },
        "riskNotes": [
            "This is an unsigned transaction. You must sign with your wallet.",
            "Actual fee depends on energy/bandwidth and network conditions.",
        ],
    }


def prepare_transaction(prompt: str) -> Dict[str, Any]:
    intent = parse_intent(prompt)
    if intent.get("action") != "TRANSFER":
        return {
            "intent": intent,
            "status": "UNSUPPORTED",
            "message": "Only TRANSFER is supported in this MVP (TRX/TRC20).",
        }

    from_addr = intent.get("from")
    to_addr = intent.get("to")
    amount = intent.get("amount")
    if not from_addr or not to_addr or not amount:
        return {
            "intent": intent,
            "status": "NEEDS_INFO",
            "message": "Need from_address, to_address, and amount in prompt.",
        }
    validate_address(from_addr)
    validate_address(to_addr)

    if intent.get("asset") == "TRC20":
        unsigned = trc20_assistant.create_unsigned_trc20_transfer(
            from_address=from_addr,
            to_address=to_addr,
            amount=amount,
            decimals=6,
        )
    else:
        unsigned = tx_assistant.create_unsigned_trx_transfer(
            from_address=from_addr,
            to_address=to_addr,
            amount_trx=amount,
        )

    return {
        "intent": intent,
        "status": "READY_TO_SIGN",
        "confirmation": _confirmation_summary(intent),
        "unsigned_tx": unsigned,
        "next_action": "Call agent_request_signature with unsigned_tx, then broadcast_signed_transaction.",
    }


def request_signature(unsigned_tx: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(unsigned_tx, dict):
        raise ValidationError("unsigned_tx must be an object")
    return {
        "signing_request": unsigned_tx,
        "instruction": "Use your wallet/HSM/MPC to sign this unsigned transaction. Do NOT share private keys.",
    }


def broadcast_signed(signed_tx: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(signed_tx, dict):
        raise ValidationError("signed_tx must be an object")
    return broadcast_transaction(signed_tx)


def prepare_trx_transfer_flow(
    from_address: str,
    to_address: str,
    amount_trx: Optional[str] = None,
    amount_sun: Optional[int | str] = None,
) -> Dict[str, Any]:
    """Build unsigned TRX transfer and wrap it as a signing request."""
    unsigned = tx_assistant.create_unsigned_trx_transfer(
        from_address=from_address,
        to_address=to_address,
        amount_trx=amount_trx,
        amount_sun=amount_sun,
    )
    return {
        "unsigned_tx": unsigned,
        "signing_request": request_signature(unsigned),
        "note": "This tool does NOT sign or broadcast. Sign manually, then call broadcast_signed_transaction.",
    }


def transfer_trx_local_sign_broadcast(
    from_address: str,
    to_address: str,
    amount_trx: Optional[str] = None,
    amount_sun: Optional[int | str] = None,
    env_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Create, sign locally, and broadcast a TRX transfer."""
    unsigned = tx_assistant.create_unsigned_trx_transfer(
        from_address=from_address,
        to_address=to_address,
        amount_trx=amount_trx,
        amount_sun=amount_sun,
    )
    signed = local_signer.sign_transaction(unsigned.get("unsignedTx", {}), env_path=env_path)
    broadcast = broadcast_signed(signed.get("signed_tx", {}))
    return {
        "unsigned_tx": unsigned,
        "signed": signed,
        "broadcast": broadcast,
        "txid": signed.get("txid"),
        "note": "Signed locally with .env.private and broadcast via TRONGRID.",
    }


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "agent_parse_intent":
        return parse_intent(args.get("prompt"))
    if name == "agent_prepare_transaction":
        return prepare_transaction(args.get("prompt"))
    if name == "agent_request_signature":
        return request_signature(args.get("unsigned_tx"))
    if name == "broadcast_signed_transaction":
        return broadcast_signed(args.get("signed_tx"))
    if name == "prepare_trx_transfer_flow":
        return prepare_trx_transfer_flow(
            from_address=args.get("from_address"),
            to_address=args.get("to_address"),
            amount_trx=args.get("amount_trx"),
            amount_sun=args.get("amount_sun"),
        )
    if name == "transfer_trx_local_sign_broadcast":
        return transfer_trx_local_sign_broadcast(
            from_address=args.get("from_address"),
            to_address=args.get("to_address"),
            amount_trx=args.get("amount_trx"),
            amount_sun=args.get("amount_sun"),
            env_path=args.get("env_path"),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="agent_parse_intent", description="Parse natural language into a structured on-chain intent.")
    def tool_agent_parse_intent(prompt: str) -> dict:
        return safety.enrich(parse_intent(prompt))

    @mcp.tool(name="agent_prepare_transaction", description="Prepare unsigned transaction with confirmation summary.")
    def tool_agent_prepare_transaction(prompt: str) -> dict:
        return safety.enrich(prepare_transaction(prompt))

    @mcp.tool(name="agent_request_signature", description="Wrap unsigned transaction as a signing request.")
    def tool_agent_request_signature(unsigned_tx: dict) -> dict:
        return safety.enrich(request_signature(unsigned_tx))

    @mcp.tool(name="broadcast_signed_transaction", description="Broadcast a signed transaction to the network.")
    def tool_broadcast_signed_transaction(signed_tx: dict) -> dict:
        return safety.enrich(broadcast_signed(signed_tx))

    @mcp.tool(
        name="prepare_trx_transfer_flow",
        description="Build unsigned TRX transfer and return signing request (no sign/broadcast).",
    )
    def tool_prepare_trx_transfer_flow(
        from_address: str,
        to_address: str,
        amount_trx: str | None = None,
        amount_sun: int | None = None,
    ) -> dict:
        return safety.enrich(
            prepare_trx_transfer_flow(
                from_address=from_address,
                to_address=to_address,
                amount_trx=amount_trx,
                amount_sun=amount_sun,
            )
        )

    @mcp.tool(
        name="transfer_trx_local_sign_broadcast",
        description="Create, sign locally, and broadcast a TRX transfer using .env.private.",
    )
    def tool_transfer_trx_local_sign_broadcast(
        from_address: str,
        to_address: str,
        amount_trx: str | None = None,
        amount_sun: int | None = None,
        env_path: str | None = None,
    ) -> dict:
        return safety.enrich(
            transfer_trx_local_sign_broadcast(
                from_address=from_address,
                to_address=to_address,
                amount_trx=amount_trx,
                amount_sun=amount_sun,
                env_path=env_path,
            )
        )
