"""Audit logging module (JSONL) for accounting/reconciliation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from tron_mcp import safety, settings
from tron_mcp.utils.errors import ValidationError
from tron_mcp import tools as core_tools
from tron_mcp.modules.audit_schema import normalize_event, SCHEMA_VERSION


def _default_audit_path() -> Path:
    base = Path(settings.SETTINGS.audit_log_dir or "logs/transactions")
    return base / "audit.jsonl"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def audit_log_event(event: Dict[str, Any], path: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(event, dict):
        raise ValidationError("event must be an object")
    out = normalize_event(event)

    audit_path = Path(path) if path else _default_audit_path()
    _ensure_parent(audit_path)
    with audit_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(out, ensure_ascii=False) + "\n")

    return {"ok": True, "path": str(audit_path), "schema": SCHEMA_VERSION, "event": out}


def audit_get_logs(limit: int = 50, path: Optional[str] = None) -> Dict[str, Any]:
    audit_path = Path(path) if path else _default_audit_path()
    if not audit_path.exists():
        return {"ok": True, "path": str(audit_path), "items": []}

    items: List[Dict[str, Any]] = []
    with audit_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                items.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if limit:
        items = items[-limit:]

    return {"ok": True, "path": str(audit_path), "count": len(items), "items": items}


def audit_reconcile(txids: List[str], path: Optional[str] = None) -> Dict[str, Any]:
    if not isinstance(txids, list) or not txids:
        raise ValidationError("txids must be a non-empty list")

    results = []
    for txid in txids:
        res = core_tools.get_tx_status(txid)
        results.append(res)

    # Log reconciliation result
    audit_log_event({"action": "reconcile", "txids": txids, "results": results}, path=path)

    return {"ok": True, "results": results}


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "audit_log_event",
        "description": "Append an audit event to JSONL log.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "event": {"type": "object"},
                "path": {"type": "string"},
            },
            "required": ["event"],
        },
    },
    {
        "name": "audit_get_logs",
        "description": "Read audit JSONL log (tail).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "limit": {"type": "integer"},
                "path": {"type": "string"},
            },
            "required": [],
        },
    },
    {
        "name": "audit_reconcile",
        "description": "Reconcile txids by querying chain status and logging results.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "txids": {"type": "array", "items": {"type": "string"}},
                "path": {"type": "string"},
            },
            "required": ["txids"],
        },
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "audit_log_event":
        return audit_log_event(event=args.get("event"), path=args.get("path"))
    if name == "audit_get_logs":
        return audit_get_logs(limit=args.get("limit", 50), path=args.get("path"))
    if name == "audit_reconcile":
        return audit_reconcile(txids=args.get("txids"), path=args.get("path"))
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="audit_log_event", description="Append an audit event to JSONL log.")
    def tool_audit_log_event(event: dict, path: str | None = None) -> dict:
        return safety.enrich(audit_log_event(event=event, path=path))

    @mcp.tool(name="audit_get_logs", description="Read audit JSONL log (tail).")
    def tool_audit_get_logs(limit: int = 50, path: str | None = None) -> dict:
        return safety.enrich(audit_get_logs(limit=limit, path=path))

    @mcp.tool(name="audit_reconcile", description="Reconcile txids by querying chain status and logging results.")
    def tool_audit_reconcile(txids: list, path: str | None = None) -> dict:
        return safety.enrich(audit_reconcile(txids=txids, path=path))
