import os
import tomli
from dotenv import load_dotenv

load_dotenv()

class Config:
    _config = {}
    
    # Load TOML if exists
    try:
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        config_path = os.path.join(project_root, "config.toml")
        with open(config_path, "rb") as f:
            _config = tomli.load(f)
            # print(f"✅ Loaded config from {config_path}")
    except FileNotFoundError:
        print(f"⚠️ Config not found at {config_path}")
        pass
        
    # Mapping
    # Logic: Env Var > TOML > Default
    
    TRONGRID_API_KEY = os.getenv("TRONGRID_API_KEY") or _config.get("trongrid_api_key")
    TRONSCAN_API_KEY = os.getenv("TRONSCAN_API_KEY") or _config.get("tronscan_api_key")
    
    # Default network configs (from TOML - currently Nile)
    TRON_NODE_URL = _config.get("trongrid_base", "https://nile.trongrid.io")
    TRONSCAN_URL = _config.get("tronscan_base", "https://nileapi.tronscan.org/api")
    
    # Network-specific configurations
    NETWORK_CONFIGS = {
        'mainnet': {
            'trongrid_url': 'https://api.trongrid.io',
            'tronscan_url': 'https://apilist.tronscanapi.com/api',
        },
        'nile': {
            'trongrid_url': 'https://nile.trongrid.io',
            'tronscan_url': 'https://nileapi.tronscan.org/api',
        },
        'shasta': {
            'trongrid_url': 'https://api.shasta.trongrid.io',
            'tronscan_url': 'https://api.shasta.tronscan.org/api',
        },
        'unknown': {
            'trongrid_url': 'https://nile.trongrid.io',  # Default to Nile
            'tronscan_url': 'https://nileapi.tronscan.org/api',
        },
    }
    
    @staticmethod
    def get_network_config(network: str = 'nile'):
        """Get network-specific configuration."""
        return Config.NETWORK_CONFIGS.get(network, Config.NETWORK_CONFIGS['nile'])
    
    USDT_CONTRACT = _config.get("usdt_contract", "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
    TIMEOUT = _config.get("request_timeout", 15.0)

    # AI Config
    AI_PROVIDER = os.getenv("AI_PROVIDER") or _config.get("ai_provider", "openai")
    AI_API_KEY = os.getenv("AI_API_KEY") or os.getenv("OPENAI_API_KEY") or _config.get("ai_api_key")
    AI_API_BASE = os.getenv("AI_API_BASE") or _config.get("ai_api_base")
    AI_MODEL = os.getenv("AI_MODEL") or _config.get("ai_model", "gpt-3.5-turbo")

    @staticmethod
    def validate():
        if not Config.TRONGRID_API_KEY:
             # Warning only
            print("Warning: TRONGRID_API_KEY not set.")
        if not Config.AI_API_KEY:
            print("Warning: AI_API_KEY not set. Smart features will be disabled.")
