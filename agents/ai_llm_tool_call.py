"""Demonstration: use AI client to call an LLM with MCP tool schema.

This does NOT start the MCP server; it shows how an external orchestrator
could supply the available tools to an LLM that supports function-calling.

Prerequisites:
    - Fill ai_api_base/ai_api_key/ai_model in config.toml or env.
    - Network access to the chosen provider.

Run:
    python3 agents/ai_llm_tool_call.py
"""

from __future__ import annotations

import json
from rich.console import Console
from rich.panel import Panel
from rich.syntax import Syntax

from tron_mcp import settings, tools
from tron_mcp.ai import call_chat
from tron_mcp.utils.errors import UpstreamError, ValidationError
from tron_mcp.utils.logging_setup import setup_logging


def main() -> None:
    setup_logging(level="INFO", logfile="logs/ai_llm_tool_call.log")
    console = Console()

    # Prepare a simple user prompt; include tool schema from MCP list_tools.
    tool_schema = tools.list_tools()["tools"]
    messages = [{"role": "user", "content": "Show me energy fee and bandwidth fee on TRON."}]

    try:
        resp = call_chat(messages, tools_schema=tool_schema)
        console.print(Panel("[bold green]AI response JSON[/]"))
        pretty = json.dumps(resp, indent=2, ensure_ascii=False)
        console.print(Syntax(pretty, "json", theme="monokai", word_wrap=True))
    except ValidationError as err:
        console.print(f"[bold red][config error][/] {err}")
    except UpstreamError as err:
        console.print(f"[bold red][provider error][/] {err}")
        if err.body:
            console.print("Raw error body (truncated to 800 chars):")
            console.print(Syntax((err.body or "")[:800], "json", theme="monokai", word_wrap=True))


if __name__ == "__main__":
    main()

# python3 -c "from tron_mcp import tools; print(tools.get_usdt_balance('TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP'))"

# python3 -c "from tron_mcp import tools; print(tools.get_network_params())"

# python3 -c "from tron_mcp import tools; print(tools.get_tx_status('17c46bf2625aaf21b28a0c54783715d63380ccdb3d1134c8365e2628a5e2f6c4'))"

# python3 -c "from tron_mcp import tools; print(tools.get_recent_transactions('TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP', limit=5))"

# python3 -c "from tron_mcp import tools; print(tools.get_trc20_transfers('TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP', limit=5))"

# python3 -c "from tron_mcp import tools; print(tools.get_address_labels('TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP'))"
