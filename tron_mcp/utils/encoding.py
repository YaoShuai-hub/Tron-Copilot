"""Encoding helpers for TRON ABI and address conversions."""

from __future__ import annotations

import hashlib
from typing import Final

from tron_mcp.utils.errors import ValidationError

_ALPHABET: Final = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
_ALPHABET_IDX = {c: i for i, c in enumerate(_ALPHABET)}


def _base58_decode(value: str) -> bytes:
    num = 0
    for ch in value:
        if ch not in _ALPHABET_IDX:
            raise ValidationError("Invalid Base58 character")
        num = num * 58 + _ALPHABET_IDX[ch]
    # Convert to bytes
    out = num.to_bytes((num.bit_length() + 7) // 8, byteorder="big") if num > 0 else b""
    # Add leading zeros
    pad = 0
    for ch in value:
        if ch == "1":
            pad += 1
        else:
            break
    return b"\x00" * pad + out


def _base58_encode(raw: bytes) -> str:
    num = int.from_bytes(raw, byteorder="big")
    out = ""
    while num > 0:
        num, rem = divmod(num, 58)
        out = _ALPHABET[rem] + out
    # Preserve leading zeros
    pad = 0
    for b in raw:
        if b == 0:
            pad += 1
        else:
            break
    return ("1" * pad) + out if out else ("1" * pad)


def tron_b58_to_hex(address: str) -> str:
    """Convert TRON Base58 address to hex (with 41 prefix)."""
    raw = _base58_decode(address)
    if len(raw) != 25:
        raise ValidationError("Invalid TRON address length")
    payload, checksum = raw[:-4], raw[-4:]
    check = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    if check != checksum:
        raise ValidationError("Invalid TRON address checksum")
    if payload[0] != 0x41:
        raise ValidationError("Invalid TRON address prefix")
    return payload.hex()


def tron_hex_to_b58(hex_address: str) -> str:
    """Convert TRON hex address (41-prefixed) to Base58Check."""
    addr = hex_address.lower().replace("0x", "")
    if len(addr) != 42:
        raise ValidationError("Invalid TRON hex address length")
    raw = bytes.fromhex(addr)
    if raw[0] != 0x41:
        raise ValidationError("Invalid TRON address prefix")
    checksum = hashlib.sha256(hashlib.sha256(raw).digest()).digest()[:4]
    return _base58_encode(raw + checksum)


def _abi_pad_hex(value_hex: str) -> str:
    value_hex = value_hex.lower().replace("0x", "")
    if len(value_hex) > 64:
        raise ValidationError("ABI value too long")
    return value_hex.rjust(64, "0")


def abi_encode_address(address: str) -> str:
    """ABI-encode a TRON address into 32-byte hex (no 0x)."""
    if address.startswith("41") and len(address) == 42:
        hex_addr = address
    elif address.startswith("0x") and len(address) == 44:
        hex_addr = address[2:]
    else:
        hex_addr = tron_b58_to_hex(address)
    return _abi_pad_hex(hex_addr)


def abi_encode_uint256(amount: int) -> str:
    if amount < 0:
        raise ValidationError("Amount must be non-negative")
    return _abi_pad_hex(hex(amount)[2:])


def encode_trc20_transfer(to_address: str, amount_raw: int) -> str:
    """ABI-encode transfer(address,uint256) parameters."""
    return abi_encode_address(to_address) + abi_encode_uint256(amount_raw)
