"""FastAPI entry point for Copilot frontend API, hosted from trident-mcp.

Re-uses the local `src/server.py` so the frontend can keep calling the same
endpoints (/chat, /api/*).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import uvicorn


def _bootstrap_copilot_app():
    project_root = Path(__file__).resolve().parent
    copilot_src = project_root / "src"
    if not copilot_src.exists():
        raise RuntimeError(f"Copilot src not found at {copilot_src}")
    # Make local src importable as top-level modules (server, config, etc).
    sys.path.insert(0, str(copilot_src))
    from server import app as copilot_app  # type: ignore

    return copilot_app


app = _bootstrap_copilot_app()


def main() -> None:
    host = os.getenv("BC_COPILOT_HOST", "0.0.0.0")
    port = int(os.getenv("BC_COPILOT_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
