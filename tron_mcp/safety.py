"""Humanization / safety enrichment for MCP tool outputs.

Goals:
- Detect common blockchain encodings (hex txid, TRON Base58 addresses) and
  add human-friendly notes without breaking existing schemas.
- Hot-pluggable: controlled by settings.safety_enable.
- Pure stdlib; no external deps.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List

from tron_mcp import settings

HEX_RE = re.compile(r"^(0x)?[0-9a-fA-F]{8,}$")
TXID_RE = re.compile(r"^[0-9a-fA-F]{64}$")
TRON_B58_RE = re.compile(r"^T[1-9A-HJ-NP-Za-km-z]{33}$")


def _classify_string(value: str) -> List[str]:
    notes: List[str] = []
    if TXID_RE.fullmatch(value):
        notes.append("Looks like TRON transaction hash (64 hex).")
    elif HEX_RE.fullmatch(value):
        notes.append(f"Hex string, {len(value) // 2 if len(value)%2==0 else len(value)} bytes (approx).")
    if TRON_B58_RE.fullmatch(value):
        notes.append("Looks like TRON Base58 address (starts with T).")
    return notes


def _walk(obj: Any, path: str, notes: List[Dict[str, str]]) -> None:
    if isinstance(obj, dict):
        for k, v in obj.items():
            _walk(v, f"{path}.{k}" if path else k, notes)
    elif isinstance(obj, list):
        for idx, v in enumerate(obj):
            _walk(v, f"{path}[{idx}]" if path else f"[{idx}]", notes)
    elif isinstance(obj, str):
        hints = _classify_string(obj)
        for hint in hints:
            notes.append({"path": path or "$", "detail": hint})


def enrich(payload: Any) -> Any:
    """Return payload with optional _human_notes array if safety is enabled."""
    if not settings.SETTINGS.safety_enable:
        return payload

    notes: List[Dict[str, str]] = []
    _walk(payload, "", notes)
    if not notes:
        return payload

    if isinstance(payload, dict):
        enriched = dict(payload)
        enriched["_human_notes"] = notes
        return enriched
    return {"data": payload, "_human_notes": notes}
