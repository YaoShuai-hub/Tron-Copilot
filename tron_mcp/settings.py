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
    tronscan_base: str = "https://nileapi.tronscan.org/api"
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
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_subscribers_path: str = "logs/telegram_subscribers.json"
    audit_log_dir: str = "logs/transactions"
    market_data_base: str = "https://api.binance.com"
    exchange_id: str | None = None
    exchange_api_key: str | None = None
    exchange_secret: str | None = None
    exchange_password: str | None = None
    exchange_api_domain: str | None = None
    exchange_proxy: str | None = None
    risk_rules_path: str | None = "risk_rules.json"
    onchain_rules_path: str | None = "onchain_rules.json"
    onchain_state_path: str | None = "logs/onchain_state.json"
    exchange_api_domain: str | None = None


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
    cfg.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", cfg.telegram_bot_token)
    cfg.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", cfg.telegram_chat_id)
    cfg.telegram_subscribers_path = os.getenv(
        "TELEGRAM_SUBSCRIBERS_PATH", cfg.telegram_subscribers_path
    )
    cfg.audit_log_dir = os.getenv("AUDIT_LOG_DIR", cfg.audit_log_dir)
    cfg.market_data_base = os.getenv("MARKET_DATA_BASE", cfg.market_data_base)
    cfg.exchange_id = os.getenv("EXCHANGE_ID", cfg.exchange_id)
    cfg.exchange_api_key = os.getenv("EXCHANGE_API_KEY", cfg.exchange_api_key)
    cfg.exchange_secret = os.getenv("EXCHANGE_SECRET", cfg.exchange_secret)
    cfg.exchange_password = os.getenv("EXCHANGE_PASSWORD", cfg.exchange_password)
    cfg.exchange_api_domain = os.getenv("EXCHANGE_API_DOMAIN", cfg.exchange_api_domain)
    cfg.exchange_proxy = os.getenv("EXCHANGE_PROXY", cfg.exchange_proxy)
    cfg.risk_rules_path = os.getenv("RISK_RULES_PATH", cfg.risk_rules_path)
    cfg.onchain_rules_path = os.getenv("ONCHAIN_RULES_PATH", cfg.onchain_rules_path)
    cfg.onchain_state_path = os.getenv("ONCHAIN_STATE_PATH", cfg.onchain_state_path)
    cfg.exchange_api_domain = os.getenv("EXCHANGE_API_DOMAIN", cfg.exchange_api_domain)
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
        cfg.exchange_id = data.get("exchange_id", cfg.exchange_id)
        cfg.exchange_api_key = data.get("exchange_api_key", cfg.exchange_api_key)
        cfg.exchange_secret = data.get("exchange_secret", cfg.exchange_secret)
        cfg.exchange_password = data.get("exchange_password", cfg.exchange_password)
        cfg.exchange_api_domain = data.get("exchange_api_domain", cfg.exchange_api_domain)
        cfg.exchange_proxy = data.get("exchange_proxy", cfg.exchange_proxy)
        cfg.risk_rules_path = data.get("risk_rules_path", cfg.risk_rules_path)
        cfg.onchain_rules_path = data.get("onchain_rules_path", cfg.onchain_rules_path)
        cfg.onchain_state_path = data.get("onchain_state_path", cfg.onchain_state_path)
        cfg.exchange_id = data.get("exchange_id", cfg.exchange_id)
        cfg.exchange_api_key = data.get("exchange_api_key", cfg.exchange_api_key)
        cfg.exchange_secret = data.get("exchange_secret", cfg.exchange_secret)
        cfg.exchange_password = data.get("exchange_password", cfg.exchange_password)
        cfg.exchange_api_domain = data.get("exchange_api_domain", cfg.exchange_api_domain)

    return _apply_env_overrides(cfg)


SETTINGS: Settings = load_config()
