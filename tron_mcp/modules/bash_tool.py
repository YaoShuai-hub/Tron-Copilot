"""Local bash command execution tool (use with care)."""

from __future__ import annotations

import time
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from tron_mcp import safety, settings
from tron_mcp.utils.errors import ValidationError


TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "name": "run_bash_command",
        "description": "Run a bash command locally (stdout/stderr captured).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Bash command to execute"},
                "cwd": {
                    "type": "string",
                    "description": "Working directory (must be inside repo; default repo root)",
                },
                "timeout_sec": {"type": "number", "description": "Timeout seconds (default 15)"},
                "max_output_chars": {"type": "integer", "description": "Max chars for stdout/stderr (default 8000)"},
            },
            "required": ["command"],
        },
    }
]

TOOL_NAMES = {t["name"] for t in TOOL_DEFINITIONS}


def _resolve_cwd(cwd: Optional[str]) -> str:
    repo_root = settings.REPO_ROOT.resolve()
    if not cwd:
        return str(repo_root)
    path = Path(cwd).expanduser().resolve()
    if not path.exists() or not path.is_dir():
        raise ValidationError("cwd must be an existing directory")
    if path != repo_root and repo_root not in path.parents:
        raise ValidationError("cwd must be inside the repo root")
    return str(path)


def _truncate(text: str, max_chars: Optional[int]) -> str:
    if max_chars is None:
        return text
    try:
        limit = int(max_chars)
    except (TypeError, ValueError):
        return text
    if limit <= 0:
        return text
    if len(text) <= limit:
        return text
    return text[:limit] + "...(truncated)"


def run_bash_command(
    command: str,
    cwd: Optional[str] = None,
    timeout_sec: Optional[float] = None,
    max_output_chars: Optional[int] = None,
) -> Dict[str, Any]:
    if not command or not isinstance(command, str):
        raise ValidationError("command must be a non-empty string")

    workdir = _resolve_cwd(cwd)
    timeout = float(timeout_sec) if timeout_sec is not None else 15.0
    start = time.time()
    try:
        proc = subprocess.run(
            ["/bin/bash", "-lc", command],
            cwd=workdir,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((time.time() - start) * 1000)
        stdout = _truncate(proc.stdout or "", max_output_chars or 8000)
        stderr = _truncate(proc.stderr or "", max_output_chars or 8000)
        return {
            "ok": proc.returncode == 0,
            "exit_code": proc.returncode,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": False,
            "command": command,
            "cwd": workdir,
            "duration_ms": duration_ms,
        }
    except subprocess.TimeoutExpired as err:
        duration_ms = int((time.time() - start) * 1000)
        stdout = _truncate((err.stdout or ""), max_output_chars or 8000)
        stderr = _truncate((err.stderr or ""), max_output_chars or 8000)
        return {
            "ok": False,
            "exit_code": None,
            "stdout": stdout,
            "stderr": stderr,
            "timed_out": True,
            "command": command,
            "cwd": workdir,
            "duration_ms": duration_ms,
            "error": f"Command timed out after {timeout:.1f}s",
        }


def call_tool(name: str, args: Optional[Dict[str, Any]]) -> Any:
    args = args or {}
    if name == "run_bash_command":
        return run_bash_command(
            command=args.get("command"),
            cwd=args.get("cwd"),
            timeout_sec=args.get("timeout_sec"),
            max_output_chars=args.get("max_output_chars"),
        )
    raise ValidationError(f"Unknown tool name: {name}")


def register_mcp_tools(mcp: Any) -> None:
    @mcp.tool(name="run_bash_command", description="Run a bash command locally (stdout/stderr captured).")
    def tool_run_bash_command(
        command: str,
        cwd: str | None = None,
        timeout_sec: float | None = None,
        max_output_chars: int | None = None,
    ) -> dict:
        return safety.enrich(
            run_bash_command(
                command=command,
                cwd=cwd,
                timeout_sec=timeout_sec,
                max_output_chars=max_output_chars,
            )
        )
