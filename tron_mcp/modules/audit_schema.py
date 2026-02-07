"""Audit schema helpers (v1)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

SCHEMA_VERSION = "audit.v1"


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_event(
    event_type: str,
    source: str = "audit",
    actor: Optional[Dict[str, Any]] = None,
    request: Optional[Dict[str, Any]] = None,
    transaction: Optional[Dict[str, Any]] = None,
    result: Optional[Dict[str, Any]] = None,
    tags: Optional[list[str]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "ts": utc_now(),
        "event_type": event_type,
        "source": source,
        "actor": actor or {},
        "request": request or {},
        "transaction": transaction or {},
        "result": result or {},
        "tags": tags or [],
        "meta": meta or {},
    }


def normalize_event(event: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize any input dict into audit.v1 schema."""
    if not isinstance(event, dict):
        raise ValueError("event must be a dict")

    # If already in schema, just fill missing fields.
    if event.get("schema_version") == SCHEMA_VERSION:
        out = dict(event)
        out.setdefault("event_id", str(uuid.uuid4()))
        out.setdefault("ts", utc_now())
        out.setdefault("event_type", "custom")
        out.setdefault("source", "audit")
        out.setdefault("actor", {})
        out.setdefault("request", {})
        out.setdefault("transaction", {})
        out.setdefault("result", {})
        out.setdefault("tags", [])
        out.setdefault("meta", {})
        return out

    event_type = event.get("event_type") or event.get("type") or event.get("action") or "custom"
    source = event.get("source") or "audit"

    # Keep original payload for traceability
    payload = dict(event)

    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": str(uuid.uuid4()),
        "ts": utc_now(),
        "event_type": event_type,
        "source": source,
        "actor": event.get("actor", {}),
        "request": event.get("request", {}),
        "transaction": event.get("transaction", {}),
        "result": event.get("result", {}),
        "tags": event.get("tags", []),
        "meta": event.get("meta", {}),
        "payload": payload,
    }
