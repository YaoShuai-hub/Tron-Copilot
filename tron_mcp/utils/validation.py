"""Validation and formatting helpers reused across tools."""

from __future__ import annotations

import re
from typing import Final

from tron_mcp.utils.errors import ValidationError

ADDRESS_RE: Final = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")


def format_token_amount(raw: str, decimals: int) -> str:
    """Convert integer string with decimals into human-readable decimal string."""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return "0"
    negative = value < 0
    value = abs(value)
    base = 10**decimals
    whole, frac = divmod(value, base)
    if frac == 0:
        text = str(whole)
    else:
        frac_str = str(frac).rjust(decimals, "0").rstrip("0")
        text = f"{whole}.{frac_str}"
    return f"-{text}" if negative else text


def validate_address(addr: str) -> None:
    """Ensure TRON Base58 address format."""
    if not addr or not ADDRESS_RE.match(addr):
        raise ValidationError("Invalid address: must be TRON Base58 starting with 'T'")


def validate_txid(txid: str) -> None:
    """Ensure txid is 64 hex chars."""
    if not txid or not re.fullmatch(r"[0-9a-fA-F]{64}", txid):
        raise ValidationError("txid must be a 64-character hexadecimal string")
