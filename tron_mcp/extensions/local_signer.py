"""Local signer tool: sign unsigned transactions using a private key file.

Security:
- Reads TRON_PRIVATE_KEY from .env.private by default.
- Never sends the private key anywhere.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from tron_mcp import safety
from tron_mcp.utils.errors import ValidationError


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "sign_transaction",
        "description": "Local-only: sign unsigned tx using TRON_PRIVATE_KEY from .env.private.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "unsigned_tx": {"type": "object", "description": "Unsigned transaction JSON"},
                "env_path": {"type": "string", "description": "Path to env file (default .env.private)"},
            },
            "required": ["unsigned_tx"],
        },
    }
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


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


def sign_transaction(unsigned_tx: Dict[str, Any], env_path: str | None = None) -> Dict[str, Any]:
    if not isinstance(unsigned_tx, dict):
        raise ValidationError("unsigned_tx must be an object")
    env_file = Path(env_path or ".env.private")
    env = _load_env_private(env_file)
    priv_hex = env.get("TRON_PRIVATE_KEY")
    if not priv_hex:
        raise ValidationError("TRON_PRIVATE_KEY not found in .env.private")

    try:
        from tronpy.keys import PrivateKey
    except Exception as err:  # noqa: BLE001
        raise ValidationError(f"tronpy not installed: {err}") from err

    txid = unsigned_tx.get("txID")
    if not txid:
        raw_hex = unsigned_tx.get("raw_data_hex")
        if not raw_hex:
            raise ValidationError("Missing txID and raw_data_hex in unsigned tx")
        txid = hashlib.sha256(bytes.fromhex(raw_hex)).hexdigest()

    priv = PrivateKey(bytes.fromhex(priv_hex))
    sig = priv.sign_msg_hash(bytes.fromhex(txid))

    signed = dict(unsigned_tx)
    signed["signature"] = [sig.hex()]
    signed["txID"] = txid
    return {"signed_tx": signed, "txid": txid}


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "sign_transaction":
        return sign_transaction(
            unsigned_tx=args.get("unsigned_tx"),
            env_path=args.get("env_path"),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(
        name="sign_transaction",
        description="Local-only: sign unsigned tx using TRON_PRIVATE_KEY from .env.private.",
    )
    def tool_sign_transaction(unsigned_tx: dict, env_path: str | None = None) -> dict:
        return safety.enrich(sign_transaction(unsigned_tx=unsigned_tx, env_path=env_path))
