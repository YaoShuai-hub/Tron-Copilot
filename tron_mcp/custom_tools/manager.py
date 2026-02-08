"""Custom tools manager (write + reload)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from tron_mcp import safety
from tron_mcp.utils.errors import ValidationError
from tron_mcp.custom_tools import reload_custom_tools


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "custom_tools_write",
        "description": "Write a custom tool module under tron_mcp/custom_tools.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_name": {"type": "string", "description": "e.g., tool_example.py"},
                "code": {"type": "string", "description": "Python module code"},
                "overwrite": {"type": "boolean"},
                "reload": {"type": "boolean"},
            },
            "required": ["file_name", "code"],
        },
    },
    {
        "name": "custom_tools_reload",
        "description": "Reload custom tools from tron_mcp/custom_tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "custom_tools_clear",
        "description": "Delete all custom tool modules under tron_mcp/custom_tools.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}

_FILE_RE = re.compile(r"^[a-zA-Z0-9_]+\.py$")


def _custom_dir() -> Path:
    return Path(__file__).resolve().parent


def custom_tools_write(file_name: str, code: str, overwrite: bool = False, reload: bool = False) -> Dict[str, Any]:
    if not file_name or not _FILE_RE.fullmatch(file_name):
        raise ValidationError("file_name must match [a-zA-Z0-9_]+.py")
    if file_name in {"__init__.py", "manager.py"} or file_name.startswith("_"):
        raise ValidationError("file_name is reserved")
    if not code or not isinstance(code, str):
        raise ValidationError("code must be a non-empty string")

    path = _custom_dir() / file_name
    if path.exists() and not overwrite:
        raise ValidationError("file exists; set overwrite=true to replace")

    path.write_text(code, encoding="utf-8")
    result = {"ok": True, "path": str(path), "reloaded": False}
    if reload:
        reload_custom_tools()
        result["reloaded"] = True
    return result


def custom_tools_reload() -> Dict[str, Any]:
    reload_custom_tools()
    return {"ok": True, "reloaded": True}


def custom_tools_clear() -> Dict[str, Any]:
    custom_dir = _custom_dir()
    deleted: List[str] = []
    for path in custom_dir.glob("*.py"):
        if path.name in {"__init__.py", "manager.py"} or path.name.startswith("_"):
            continue
        path.unlink(missing_ok=True)
        deleted.append(path.name)
    reload_custom_tools()
    return {"ok": True, "deleted": deleted}


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "custom_tools_write":
        return custom_tools_write(
            file_name=args.get("file_name"),
            code=args.get("code"),
            overwrite=bool(args.get("overwrite")),
            reload=bool(args.get("reload")),
        )
    if name == "custom_tools_reload":
        return custom_tools_reload()
    if name == "custom_tools_clear":
        return custom_tools_clear()
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="custom_tools_write", description="Write a custom tool module under tron_mcp/custom_tools.")
    def tool_custom_tools_write(
        file_name: str,
        code: str,
        overwrite: bool = False,
        reload: bool = False,
    ) -> dict:
        return safety.enrich(
            custom_tools_write(file_name=file_name, code=code, overwrite=overwrite, reload=reload)
        )

    @mcp.tool(name="custom_tools_reload", description="Reload custom tools from tron_mcp/custom_tools.")
    def tool_custom_tools_reload() -> dict:
        return safety.enrich(custom_tools_reload())

    @mcp.tool(name="custom_tools_clear", description="Delete all custom tools under tron_mcp/custom_tools.")
    def tool_custom_tools_clear() -> dict:
        return safety.enrich(custom_tools_clear())
