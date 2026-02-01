"""
Textual-based TUI for Trident MCP.

Features:
- Persistent pane layout:
    * Left: Conversation log (rich text).
    * Right: Tool trace/results (rich text).
    * Bottom: Prompt input with status bar.
- Uses existing tool orchestration (agent_chat) for multi-round tool calls.
- Runs entirely locally; requires `textual` package.

Run:
    cd HK_hacker_26/trident-mcp
    source .venv/bin/activate
    .venv/bin/pip install textual
    python -m agents.tui_app
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, List

from textual import events
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal
from textual.message import Message
from textual.reactive import reactive
from textual.widgets import Footer, Input, Static

from agents.agent_runner import agent_chat


class ChatPane(Static):
    """Pane to render conversation text."""

    def on_mount(self) -> None:  # type: ignore[override]
        self._text: str = ""

    def append(self, text: str) -> None:
        self._text = f"{self._text}\n{text}" if self._text else text
        self.update(self._text)


class TracePane(Static):
    """Pane to render trace/tool results."""

    def render_trace(self, result: Dict[str, Any]) -> None:
        lines: List[str] = []
        for step in result.get("trace", []):
            round_no = step.get("round")
            msg = step.get("response", {}).get("choices", [{}])[0].get("message", {})
            lines.append(f"[b]Round {round_no}[/] content: {msg.get('content')}")
            for call in msg.get("tool_calls") or []:
                fn = call.get("function", {}) or {}
                lines.append(f"  [yellow]call[/] {fn.get('name')} args={fn.get('arguments')}")
        final = result.get("final", {}).get("content")
        if final:
            lines.append(f"[green]Final:[/] {final}")
        self.update("\n".join(lines) if lines else "(no trace)")


class StatusBar(Static):
    """Simple status bar."""

    text = reactive("Ready")

    def watch_text(self, text: str) -> None:
        self.update(f"[dim]{text}")


class AgentTUI(App):
    CSS = """
    Screen {
        layout: vertical;
        background: #0f0f14;
        color: #c7d5e0;
    }
    #body {
        layout: horizontal;
        height: 1fr;
    }
    ChatPane {
        border: solid #7a3ff2;
        padding: 1 1;
        width: 1fr;
        height: 1fr;
    }
    TracePane {
        border: solid #29b6f6;
        padding: 1 1;
        width: 1fr;
        height: 1fr;
    }
    #input-row {
        layout: horizontal;
        padding: 1;
        height: 3;
        border: solid #444;
    }
    Input {
        width: 1fr;
        border: solid #7a3ff2;
    }
    StatusBar {
        height: 1;
        padding: 0 1;
        color: #888;
    }
    """

    BINDINGS = [("ctrl+c", "quit", "Quit")]

    class Submitted(Message):
        def __init__(self, text: str) -> None:
            self.text = text
            super().__init__()

    def compose(self) -> ComposeResult:
        self.chat = ChatPane(id="chat")
        self.trace = TracePane(id="trace")
        self.status = StatusBar(id="status")
        self.input = Input(placeholder="Ask about TRON... (exit/quit to leave)")

        yield Container(
            Horizontal(self.chat, self.trace, id="body"),
        )
        yield Container(self.input, id="input-row")
        yield Footer()
        yield self.status

    async def on_mount(self) -> None:
        self.input.focus()
        self.chat.append("[b cyan]Trident MCP Agent[/] ready. Ask me anything about TRON.")

    async def handle_submit(self, text: str) -> None:
        text = text.strip()
        if not text:
            return
        if text.lower() in {"exit", "quit"}:
            await self.action_quit()
            return

        self.chat.append(f"[magenta]You:[/] {text}")
        self.status.text = "Calling LLM + tools..."

        # Run agent_chat in thread to avoid blocking UI event loop
        result = await asyncio.to_thread(agent_chat, text, 3)

        # Append LLM reply
        final = result.get("final", {}).get("content") or "(no final message)"
        self.chat.append(f"[cyan]Assistant:[/] {final}")
        self.trace.render_trace(result)
        self.status.text = "Ready"

    async def on_input_submitted(self, event: Input.Submitted) -> None:  # type: ignore[override]
        await self.handle_submit(event.value)
        self.input.value = ""

    async def on_key(self, event: events.Key) -> None:
        if event.key == "enter" and self.input.has_focus:
            await self.handle_submit(self.input.value)
            self.input.value = ""


if __name__ == "__main__":
    AgentTUI().run()
