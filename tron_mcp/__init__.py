"""
TRON MCP Server package (tron_mcp).

Provides a small MCP server exposing TRON data as tools.
Modules are organized so each concern (settings, AI client, API, tools, safety, FastMCP runtime)
can be tested or replaced independently.
"""

from .settings import SETTINGS

__all__ = [
    "settings",
    "ai",
    "tron_api",
    "tools",
    "safety",
    "utils",
    "SETTINGS",
]
