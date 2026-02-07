"""Extended tool: build unsigned TRX transfer transactions."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Dict, List, Optional

from tron_mcp import safety
from tron_mcp.tron_api import create_trx_transfer
from tron_mcp.utils.errors import ValidationError
from tron_mcp.utils.validation import format_token_amount, validate_address


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "create_unsigned_trx_transfer",
        "description": "Create an unsigned TRX transfer transaction (TRONGRID).",
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
    }
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def _amount_to_sun(amount_trx: Optional[str], amount_sun: Optional[int | str]) -> int:
    """Normalize TRX amount to sun (int)."""
    if amount_sun not in (None, ""):
        try:
            sun = int(amount_sun)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            raise ValidationError("amount_sun must be an integer") from None
        if sun <= 0:
            raise ValidationError("amount_sun must be > 0")
        return sun

    if amount_trx in (None, ""):
        raise ValidationError("Provide amount_trx or amount_sun")
    try:
        trx = Decimal(str(amount_trx))
    except (InvalidOperation, ValueError):
        raise ValidationError("amount_trx must be a valid decimal string") from None
    if trx <= 0:
        raise ValidationError("amount_trx must be > 0")
    sun = (trx * Decimal(1_000_000)).quantize(Decimal("1"), rounding=ROUND_DOWN)
    return int(sun)


def create_unsigned_trx_transfer(
    from_address: str,
    to_address: str,
    amount_trx: Optional[str] = None,
    amount_sun: Optional[int | str] = None,
) -> Dict[str, Any]:
    """Create an unsigned TRX transfer transaction."""
    validate_address(from_address)
    validate_address(to_address)
    sun = _amount_to_sun(amount_trx, amount_sun)
    tx = create_trx_transfer(from_address, to_address, sun)
    return {
        "from": from_address,
        "to": to_address,
        "amountSun": sun,
        "amountTrx": format_token_amount(str(sun), 6),
        "txid": tx.get("txID"),
        "unsignedTx": tx,
        "source": "TRONGRID",
        "note": "Unsigned transaction. Sign and broadcast with a wallet/private key.",
    }


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    """Dispatch extension tools by name."""
    args = args or {}
    if name == "create_unsigned_trx_transfer":
        return create_unsigned_trx_transfer(
            from_address=args.get("from_address"),
            to_address=args.get("to_address"),
            amount_trx=args.get("amount_trx"),
            amount_sun=args.get("amount_sun"),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    """Register extension tools on FastMCP instance."""

    @mcp.tool(
        name="create_unsigned_trx_transfer",
        description="Create an unsigned TRX transfer transaction (TRONGRID).",
    )
    def tool_create_unsigned_trx_transfer(
        from_address: str,
        to_address: str,
        amount_trx: str | None = None,
        amount_sun: int | None = None,
    ) -> dict:
        return safety.enrich(
            create_unsigned_trx_transfer(
                from_address=from_address,
                to_address=to_address,
                amount_trx=amount_trx,
                amount_sun=amount_sun,
            )
        )

