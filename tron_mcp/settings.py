"""Configuration loader.

Order: read `config.toml` at repo root, then override with environment variables,
and expose a read-only `SETTINGS`. Suitable for container/local/CI without
hard-coding constants.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import tomllib


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = REPO_ROOT / "config.toml"


@dataclass
class Settings:
    port: int = 8787
    tronscan_base: str = "https://nileapi.tronscan.org"
    trongrid_base: str = "https://nile.trongrid.io"
    tronscan_api_key: str = ""
    trongrid_api_key: str = ""
    usdt_contract: str = "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t"
    coingecko_base: str = "https://api.coingecko.com/api/v3"
    request_timeout: float = 12.0  # seconds
    log_level: str = "INFO"
    log_file: str | None = "logs/trident.log"  # None or empty => stdout only
    ai_api_base: str | None = None  # e.g., https://api.openai.com/v1
    ai_api_key: str | None = None
    ai_model: str | None = None
    ai_provider: str = "openai"  # openai | azure-openai | anthropic | custom
    safety_enable: bool = True


def _apply_env_overrides(cfg: Settings) -> Settings:
    """Override settings with environment variables for runtime flexibility."""
    cfg.port = int(os.getenv("PORT", cfg.port))
    cfg.tronscan_base = os.getenv("TRONSCAN_BASE", cfg.tronscan_base)
    cfg.trongrid_base = os.getenv("TRONGRID_BASE", cfg.trongrid_base)
    cfg.tronscan_api_key = os.getenv("TRONSCAN_API_KEY", cfg.tronscan_api_key)
    cfg.trongrid_api_key = os.getenv(
        "TRONGRID_API_KEY", os.getenv("TRON_PRO_API_KEY", cfg.trongrid_api_key)
    )
    cfg.usdt_contract = os.getenv("TRON_USDT_CONTRACT", cfg.usdt_contract)
    cfg.coingecko_base = os.getenv("COINGECKO_BASE", cfg.coingecko_base)
    timeout_ms = os.getenv("REQUEST_TIMEOUT_MS")
    if timeout_ms:
        try:
            cfg.request_timeout = float(timeout_ms) / 1000.0
        except ValueError:
            pass
    cfg.log_level = os.getenv("LOG_LEVEL", cfg.log_level).upper()
    cfg.log_file = os.getenv("LOG_FILE", cfg.log_file or "") or None
    cfg.ai_api_base = os.getenv("AI_API_BASE", cfg.ai_api_base)
    cfg.ai_api_key = os.getenv("AI_API_KEY", cfg.ai_api_key)
    cfg.ai_model = os.getenv("AI_MODEL", cfg.ai_model)
    cfg.ai_provider = os.getenv("AI_PROVIDER", cfg.ai_provider)
    safety_env = os.getenv("SAFETY_ENABLE")
    if safety_env is not None:
        cfg.safety_enable = safety_env.lower() in {"1", "true", "yes", "on"}
    return cfg


def load_config(path: Path | None = None) -> Settings:
    path = path or DEFAULT_CONFIG_PATH
    cfg = Settings()

    if path.exists():
        with path.open("rb") as f:
            data = tomllib.load(f)
        # Apply values from TOML; fall back to defaults if missing
        cfg.port = int(data.get("port", cfg.port))
        cfg.tronscan_base = data.get("tronscan_base", cfg.tronscan_base)
        cfg.trongrid_base = data.get("trongrid_base", cfg.trongrid_base)
        cfg.tronscan_api_key = data.get("tronscan_api_key", cfg.tronscan_api_key)
        cfg.trongrid_api_key = data.get("trongrid_api_key", cfg.trongrid_api_key)
        cfg.usdt_contract = data.get("usdt_contract", cfg.usdt_contract)
        cfg.coingecko_base = data.get("coingecko_base", cfg.coingecko_base)
        cfg.request_timeout = float(data.get("request_timeout", cfg.request_timeout))
        cfg.log_level = str(data.get("log_level", cfg.log_level)).upper()
        cfg.log_file = data.get("log_file") or None
        cfg.ai_api_base = data.get("ai_api_base", cfg.ai_api_base)
        cfg.ai_api_key = data.get("ai_api_key", cfg.ai_api_key)
        cfg.ai_model = data.get("ai_model", cfg.ai_model)
        cfg.ai_provider = data.get("ai_provider", cfg.ai_provider)
        if "safety_enable" in data:
            cfg.safety_enable = bool(data.get("safety_enable"))

    return _apply_env_overrides(cfg)


SETTINGS: Settings = load_config()
