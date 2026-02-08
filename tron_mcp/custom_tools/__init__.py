"""Dynamic custom tools loader."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from tron_mcp.utils.errors import ValidationError

BASE_DIR = Path(__file__).resolve().parent

_REGISTRY: Dict[str, Any] = {
    "definitions": [],
    "dispatch": {},
    "modules": {},
}


def _iter_tool_modules() -> List[str]:
    modules = []
    for path in BASE_DIR.glob("*.py"):
        if path.name in {"__init__.py"}:
            continue
        if path.name.startswith("_"):
            continue
        modules.append(f"tron_mcp.custom_tools.{path.stem}")
    return sorted(modules)


def load_custom_tools(reload: bool = False) -> Dict[str, Any]:
    definitions: List[Dict[str, Any]] = []
    dispatch: Dict[str, Any] = {}
    modules: Dict[str, Any] = {}

    for mod_name in _iter_tool_modules():
        try:
            if reload and mod_name in sys.modules:
                mod = importlib.reload(sys.modules[mod_name])
            else:
                mod = importlib.import_module(mod_name)
        except Exception:
            continue

        tool_defs = getattr(mod, "TOOL_DEFINITIONS", None)
        call_tool = getattr(mod, "call_tool", None)
        if not isinstance(tool_defs, list) or not callable(call_tool):
            continue

        for tool in tool_defs:
            name = (tool or {}).get("name")
            if name:
                dispatch[name] = call_tool
                definitions.append(tool)
        modules[mod_name] = mod

    _REGISTRY["definitions"] = definitions
    _REGISTRY["dispatch"] = dispatch
    _REGISTRY["modules"] = modules
    return _REGISTRY


def reload_custom_tools() -> Dict[str, Any]:
    return load_custom_tools(reload=True)


def get_tool_definitions() -> List[Dict[str, Any]]:
    if not _REGISTRY.get("definitions"):
        load_custom_tools(reload=False)
    return list(_REGISTRY.get("definitions") or [])


def get_tool_names() -> set[str]:
    return {t.get("name") for t in get_tool_definitions() if t.get("name")}


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    if not _REGISTRY.get("dispatch"):
        load_custom_tools(reload=False)
    fn = (_REGISTRY.get("dispatch") or {}).get(name)
    if not fn:
        raise ValidationError(f"Unknown custom tool name: {name}")
    return fn(name, args or {})
