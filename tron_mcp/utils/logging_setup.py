"""Standard logging initialization."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

from tron_mcp import settings


def setup_logging(
    level: str | int | None = None,
    logfile: Optional[str] = None,
    console: bool = True,
) -> None:
    """Initialize root logger with optional console + optional rotating file."""
    lvl = level or settings.SETTINGS.log_level
    if isinstance(lvl, str):
        lvl = getattr(logging, lvl.upper(), logging.INFO)

    handlers = []

    if logfile:
        log_path = Path(logfile).expanduser()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(
            RotatingFileHandler(log_path, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8")
        )

    if console:
        console_handler = logging.StreamHandler()
        handlers.append(console_handler)

    logging.basicConfig(
        level=lvl,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )
