"""Minimal MCP agent loop demo.

What it does:
1) Sends a user prompt + tool schema to the configured LLM.
2) If the LLM returns tool_calls, executes them with local MCP tools.
3) Feeds tool results back to the LLM for a final answer (or repeats).

Run:
    cd ~/Documents/ctf/blockchain/program/HK_hacker_26/trident-mcp
    source .venv/bin/activate
    python -m demos.agent_runner "Show me the TRON energy and bandwidth fees."

Notes:
- Uses tron_mcp.tools.call_tool for execution; no MCP server needed.
- Respects ai_* settings from config.toml/env.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
from typing import Any, Dict, List, Optional

from tron_mcp import tools
from tron_mcp.ai import call_chat
from tron_mcp.utils.errors import UpstreamError, ValidationError
from tron_mcp.utils.logging_setup import setup_logging
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.columns import Columns

# Optional nicer input (prompt_toolkit). Falls back to standard input if missing.
try:
    from prompt_toolkit import prompt as pt_prompt
    from prompt_toolkit.styles import Style as PTStyle
    PROMPT_TOOLKIT_AVAILABLE = True
except Exception:
    PROMPT_TOOLKIT_AVAILABLE = False


log = logging.getLogger("agent_runner")
console = Console()

SYSTEM_TOOL_POLICY = (
    "If the available tools cannot solve the task, you may create a new custom tool by "
    "calling custom_tools_write with a Python module (define TOOL_DEFINITIONS and call_tool), "
    "then call custom_tools_reload, and then use the new tool. "
    "If the tool is buggy, iteratively rewrite it and reload."
)

def heuristic_fallback(prompt: str) -> Dict[str, Any] | None:
    """If LLM fails, try to dispatch tools directly based on simple keywords."""
    import re

    addr_match = re.search(r"(T[1-9A-HJ-NP-Za-km-z]{33})", prompt)
    txid_match = re.search(r"\b[0-9a-fA-F]{64}\b", prompt)
    addr = addr_match.group(1) if addr_match else None

    p = prompt.lower()
    wants_total_value = any(
        phrase in p
        for phrase in (
            "total value",
            "portfolio",
            "总价值",
            "总价",
            "所有币",
            "总资产",
            "总资产价值",
            "总市值",
        )
    )
    currency = "usd"
    if "cny" in p or "rmb" in p or "人民币" in prompt:
        currency = "cny"
    elif "usd" in p or "美元" in prompt or "美金" in prompt:
        currency = "usd"
    try:
        if "trc20" in p or "transfer" in p:
            if addr:
                return {"tool": "get_trc20_transfers", "result": tools.get_trc20_transfers(addr, limit=5)}
        if "transaction" in p and ("last" in p or "latest" in p):
            if addr:
                return {"tool": "get_recent_transactions", "result": tools.get_recent_transactions(addr, limit=5)}
        if txid_match:
            return {"tool": "get_tx_status", "result": tools.get_tx_status(txid_match.group(0))}
        if wants_total_value and addr:
            return {"tool": "get_total_value", "result": tools.get_total_value(addr, currency=currency)}
        if "balance" in p and addr:
            return {"tool": "get_usdt_balance", "result": tools.get_usdt_balance(addr)}
        if "network" in p:
            return {"tool": "get_network_params", "result": tools.get_network_params()}
        if "label" in p and addr:
            return {"tool": "get_address_labels", "result": tools.get_address_labels(addr)}
    except Exception as err:  # noqa: BLE001
        return {"tool": "error", "result": f"fallback failed: {err}"}
    return None


def typewriter(text: str, style: str = "cyan", delay: float = 0.01) -> None:
    """Print text with a typewriter animation."""
    for ch in text:
        console.print(ch, style=style, end="", soft_wrap=True)
        time.sleep(delay)
    console.print("")  # newline


def pulse(label: str = "Sending...", duration: float = 0.6) -> None:
    """Small spinner animation for visual feedback."""
    with console.status(f"[cyan]{label}", spinner="dots"):
        time.sleep(duration)


def show_intro(log_path: str) -> None:
    """Render a welcoming, colorful intro banner."""
    hero = r"""
   ______     _     _           _         __  __  _____ _____
  |__  /\ \  | |__ | | ___  ___| |_ ___  |  \/  |/ ____|  __ \
    / /  \ \ | '_ \| |/ _ \/ __| __/ _ \ | \  / | |    | |  | |
   / /__  \ \| |_) | |  __/\__ \ ||  __/ | |\/| | |    | |  | |
  /_____|  \_\_.__/|_|\___||___/\__\___| |_|  |_|\_____|_|  |_|
"""
    console.print(Panel(hero, style="bold magenta", border_style="cyan", padding=(1, 2)))

    meta = Table.grid(padding=1)
    meta.add_column(justify="right", style="bold cyan")
    meta.add_column(style="white")
    meta.add_row("Mode", "Interactive · tool-enabled LLM chat")
    meta.add_row("Commands", "[white]Type your question[/] • [yellow]exit/quit[/] to leave • [dim]Ctrl+C[/] to abort")
    meta.add_row("Logs", f"[dim]{log_path}[/]")
    meta.add_row(
        "Input",
        "[green]prompt_toolkit[/] styled prompt"
        if PROMPT_TOOLKIT_AVAILABLE
        else "[yellow]basic input[/] (install prompt_toolkit for better prompt UI)",
    )

    console.print(Panel(meta, title="Session Info", border_style="green", padding=(1, 2)))
    console.print("[bold green]Ready![/] Ask me anything about TRON or type [yellow]exit[/]/[yellow]quit[/] to end.\n")


def get_user_input() -> str:
    """Prompt user; use prompt_toolkit if available for nicer styling."""
    if PROMPT_TOOLKIT_AVAILABLE:
        style = PTStyle.from_dict(
            {
                "prompt": "bold magenta",
                "toolbar": "italic #777777",
            }
        )
        return pt_prompt(
            [("class:prompt", "You ▸ ")],
            multiline=False,
            style=style,
            bottom_toolbar=lambda: "Enter to send · exit/quit to leave",
        )
    # fallback to rich console input
    return console.input("[bold magenta]You > [/]")


def exec_tool_call(name: str, arguments_json: str) -> Dict[str, Any]:
    """Execute a single tool call and return a serializable result."""
    try:
        args = json.loads(arguments_json or "{}")
    except json.JSONDecodeError as err:
        return {"error": f"Invalid arguments JSON: {err}", "raw": arguments_json}
    try:
        return tools.call_tool(name, args)
    except Exception as err:  # noqa: BLE001
        return {"error": f"Tool execution failed: {err}"}


def agent_chat(
    user_prompt: Optional[str] = None,
    messages: Optional[List[Dict[str, Any]]] = None,
    max_rounds: int = 999,
    debug: bool = False,
) -> Dict[str, Any]:
    """Run a tool-enabled chat loop; continue until no tool calls or safety cap."""
    tool_schema = tools.list_tools()["tools"]
    if messages is None:
        if not user_prompt:
            raise ValidationError("user_prompt is required when messages is not provided")
        messages = [{"role": "system", "content": SYSTEM_TOOL_POLICY}, {"role": "user", "content": user_prompt}]
    elif user_prompt:
        if not any(m.get("role") == "system" for m in messages):
            messages.insert(0, {"role": "system", "content": SYSTEM_TOOL_POLICY})
        messages.append({"role": "user", "content": user_prompt})

    trace: List[Dict[str, Any]] = []
    last_tool_results: List[Dict[str, Any]] = []

    last_tool_panel: Panel | None = None

    # Live view for structured steps
    tree = Tree("[bold cyan]Conversation Steps[/]")

    for round_idx in range(1, max_rounds + 1):
        log.info("LLM request round %s", round_idx)
        if debug:
            console.print("[dim]>> LLM request messages:[/]")
            console.print_json(data=messages)
        try:
            resp = call_chat(messages, tools_schema=tool_schema)
        except UpstreamError as err:
            return {
                "trace": trace,
                "final": {
                    "role": "assistant",
                    "content": (
                        f"LLM error: {err}"
                        + (f". Raw tool results: {json.dumps(last_tool_results, ensure_ascii=False)}"
                           if last_tool_results
                           else "")
                    ),
                },
                "tree": tree,
                "last_tool_panel": last_tool_panel,
                "messages": messages,
            }
        if debug:
            console.print("[dim]<< LLM raw response:[/]")
            console.print_json(data=resp)
        trace.append({"round": round_idx, "response": resp})

        choice = resp.get("choices", [{}])[0]
        message = choice.get("message", {})
        tool_calls = message.get("tool_calls") or []

        round_node = tree.add(f"[bold cyan]Round {round_idx}[/] · reply:")
        if message.get("content"):
            round_node.add(f"[cyan]{message.get('content')}")

        if not tool_calls:
            return {"trace": trace, "final": message, "tree": tree, "last_tool_panel": last_tool_panel, "messages": messages}

        tool_results: List[Dict[str, Any]] = []
        # Execute tool calls and append their outputs.
        for call in tool_calls:
            name = call.get("function", {}).get("name")
            arguments = call.get("function", {}).get("arguments", "{}")
            log.info("Executing tool '%s' with arguments: %s", name, arguments)

            tool_node = round_node.add(f"[yellow]→ call[/] {name} args={arguments}")
            result = exec_tool_call(name, arguments)
            log.info("Tool '%s' result: %s", name, result)

            # Pretty table for tool result (top-level keys only to keep concise)
            tbl = Table(box=None, show_header=False, expand=True)
            for k, v in result.items():
                if isinstance(v, (dict, list)):
                    payload = json.dumps(v, ensure_ascii=False)
                    display = payload[:180] + ("…" if len(payload) > 180 else "")
                else:
                    display = v
                tbl.add_row(f"[green]{k}", f"{display}")
            tool_panel = Panel(tbl, title=f"[green]✔ {name} result[/]", border_style="green")
            tool_node.add(tool_panel)
            last_tool_panel = tool_panel

            messages.append(
                {
                    "role": "assistant",
                    "tool_calls": [call],  # echo back the tool call for context
                    "content": message.get("content", ""),
                }
            )
            tool_results.append({"call": call, "result": result})
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id"),
                    "name": name,
                    "content": json.dumps(result, ensure_ascii=False),
                }
            )

        last_tool_results = tool_results
        # Continue loop so the model can decide to call more tools or stop.
    return {
        "trace": trace,
        "final": {"role": "assistant", "content": "Stopped after safety cap."},
        "tree": tree,
        "last_tool_panel": last_tool_panel,
        "messages": messages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a tool-enabled LLM agent loop.")
    parser.add_argument("--prompt", help="Run a single prompt then exit (skips REPL).")
    parser.add_argument("--rounds", type=int, default=999, help="Safety cap for tool-call rounds (default: 999).")
    parser.add_argument(
        "--log-file",
        default="logs/agent_runner.log",
        help="Path to log file (default: logs/agent_runner.log)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Print raw LLM request/response and tool calls.",
    )
    args = parser.parse_args()

    # File logging; keep console clean (color output handled by rich)
    setup_logging(level="INFO", logfile=args.log_file, console=False)
    show_intro(args.log_file)

    def run_once(prompt: str, messages: Optional[List[Dict[str, Any]]] = None) -> List[Dict[str, Any]]:
        # Echo user input in a panel; status spinner will clear automatically
        console.print(Panel(prompt, title="[magenta]You[/]", border_style="magenta", expand=True))
        with console.status("[cyan]Sending...", spinner="dots"):
            try:
                result = agent_chat(prompt, messages=messages, max_rounds=args.rounds, debug=args.debug)
            except (UpstreamError, ValidationError, Exception) as err:
                raw_body = getattr(err, "body", None)
                console.print("[bold yellow][LLM raw response][/]:")
                if raw_body:
                    try:
                        console.print_json(data=json.loads(raw_body))
                    except Exception:
                        console.print(raw_body)
                else:
                    console.print("[dim]No raw response (timeout/network error).[/]")
                fb = heuristic_fallback(prompt)
                if fb:
                    console.print(f"[green]✔ Fallback tool[/] {fb.get('tool')}:")
                    console.print_json(data=fb.get("result"))
                else:
                    console.print(
                        "[red]No heuristic fallback matched this prompt. "
                        "Try a more explicit request (include address + amount), "
                        "or call a tool directly (e.g., get_trx_balance, get_total_value, "
                        "create_unsigned_trx_transfer).[/]"
                    )
                return messages or []

        # Pretty, terminal-friendly output (compact)
        console.print("")
        console.print("[bold underline]Agent Trace[/]")
        trace_panel = Panel(result.get("tree"), title="Trace", border_style="cyan", expand=True)
        panels = [trace_panel]
        if result.get("last_tool_panel"):
            panels.append(result["last_tool_panel"])
        console.print(Columns(panels, equal=True, expand=True))

        console.print("[bold underline]Final Message[/]")
        final_content = result.get("final", {}).get("content", "")
        if final_content:
            typewriter(final_content, style="bold white", delay=0.008)
        else:
            console.print_json(data=result.get("final"))
        console.print(f"\n[dim]Logs written to: {args.log_file}[/]")
        return result.get("messages", messages or [])

    if args.prompt:
        run_once(args.prompt)
        return 0

    # Interactive REPL mode
    try:
        conversation_messages: List[Dict[str, Any]] = []
        while True:
            user_prompt = get_user_input()
            if user_prompt.strip().lower() in {"exit", "quit"}:
                break
            if not user_prompt.strip():
                continue
            # In fallback mode (no prompt_toolkit) clear the raw echo line
            if not PROMPT_TOOLKIT_AVAILABLE:
                console.print("\033[F\033[K", end="")
            conversation_messages = run_once(user_prompt, messages=conversation_messages)
    except KeyboardInterrupt:
        console.print("\n[dim]Session ended by user.[/]")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

# Example tool calls you can try in the REPL:
# Q1: Show me the current TRON network energy fee and bandwidth fee.
# Q2: Check the USDT balance of TPwjKc2nfSb6Zxk4sZDSZu6f9QaK3xktAP.
# Q3: Is transaction 17c46bf2625aaf21b28a0c54783715d63380ccdb3d1134c8365e2628a5e2f6c4 confirmed?
# Q4: List the last 5 transactions for address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.
# Q5: Show the latest 5 TRC20 transfers involving address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF.
# Q6: What labels or flags does TRON address THb4CqiFdwNHsWsQCs4JhzwjMWys4aqCbF have?
