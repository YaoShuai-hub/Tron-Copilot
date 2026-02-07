"""Extended tool: build unsigned TRC20 transfer transactions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Dict, List, Optional

from tron_mcp import safety, settings
from tron_mcp.tron_api import trigger_smart_contract
from tron_mcp.utils import format_token_amount, validate_address
from tron_mcp.utils.encoding import encode_trc20_transfer
from tron_mcp.utils.errors import ValidationError


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "create_unsigned_trc20_transfer",
        "description": "Build unsigned TRC20 transfer (manual sign + broadcast required).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "from_address": {"type": "string", "description": "Sender TRON Base58 address"},
                "to_address": {"type": "string", "description": "Recipient TRON Base58 address"},
                "token_contract": {"type": "string", "description": "TRC20 contract address (Base58 or hex)"},
                "amount": {"type": "string", "description": "Human-readable amount (e.g., '1.25')"},
                "amount_raw": {"type": "string", "description": "Raw integer amount (token decimals applied)"},
                "decimals": {"type": "integer", "description": "Token decimals (required if amount provided)"},
                "fee_limit": {"type": "integer", "description": "Fee limit in sun (default 30 TRX)"},
            },
            "required": ["from_address", "to_address"],
        },
    }
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def _amount_to_raw(amount: Optional[str], amount_raw: Optional[str], decimals: Optional[int]) -> int:
    if amount_raw not in (None, ""):
        try:
            raw = int(amount_raw)
        except (TypeError, ValueError):
            raise ValidationError("amount_raw must be an integer string") from None
        if raw <= 0:
            raise ValidationError("amount_raw must be > 0")
        return raw

    if amount in (None, ""):
        raise ValidationError("Provide amount or amount_raw")
    if decimals is None:
        raise ValidationError("decimals is required when using amount")
    try:
        qty = Decimal(str(amount))
    except (InvalidOperation, ValueError):
        raise ValidationError("amount must be a valid decimal string") from None
    if qty <= 0:
        raise ValidationError("amount must be > 0")
    raw = (qty * (Decimal(10) ** int(decimals))).quantize(Decimal("1"), rounding=ROUND_DOWN)
    return int(raw)


def create_unsigned_trc20_transfer(
    from_address: str,
    to_address: str,
    token_contract: Optional[str] = None,
    amount: Optional[str] = None,
    amount_raw: Optional[str] = None,
    decimals: Optional[int] = None,
    fee_limit: Optional[int] = None,
) -> Dict[str, Any]:
    validate_address(from_address)
    validate_address(to_address)
    contract = token_contract or settings.SETTINGS.usdt_contract
    raw_amount = _amount_to_raw(amount, amount_raw, decimals)
    param = encode_trc20_transfer(to_address, raw_amount)
    resp = trigger_smart_contract(
        owner_address=from_address,
        contract_address=contract,
        function_selector="transfer(address,uint256)",
        parameter=param,
        fee_limit=fee_limit or 30_000_000,
        call_value=0,
        visible=True,
    )
    tx = resp.get("transaction") or resp.get("transactionRaw") or resp
    return {
        "from": from_address,
        "to": to_address,
        "tokenContract": contract,
        "amountRaw": str(raw_amount),
        "amountHuman": format_token_amount(str(raw_amount), int(decimals or 6)),
        "decimals": decimals,
        "txid": (tx or {}).get("txID"),
        "unsignedTx": tx,
        "source": "TRONGRID",
        "note": "Unsigned transaction. Sign and broadcast with a wallet/private key.",
        "raw": resp,
    }


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "create_unsigned_trc20_transfer":
        return create_unsigned_trc20_transfer(
            from_address=args.get("from_address"),
            to_address=args.get("to_address"),
            token_contract=args.get("token_contract"),
            amount=args.get("amount"),
            amount_raw=args.get("amount_raw"),
            decimals=args.get("decimals"),
            fee_limit=args.get("fee_limit"),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(
        name="create_unsigned_trc20_transfer",
        description="Build unsigned TRC20 transfer (manual sign + broadcast required).",
    )
    def tool_create_unsigned_trc20_transfer(
        from_address: str,
        to_address: str,
        token_contract: str | None = None,
        amount: str | None = None,
        amount_raw: str | None = None,
        decimals: int | None = None,
        fee_limit: int | None = None,
    ) -> dict:
        return safety.enrich(
            create_unsigned_trc20_transfer(
                from_address=from_address,
                to_address=to_address,
                token_contract=token_contract,
                amount=amount,
                amount_raw=amount_raw,
                decimals=decimals,
                fee_limit=fee_limit,
            )
        )

