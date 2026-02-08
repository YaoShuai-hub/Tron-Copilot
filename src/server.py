"""
FastAPI HTTP Server for BlockChain Copilot
Provides REST API for frontend communication with TRON skills integration
"""

import os
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from config import Config
from tron_mcp import tools as tron_tools
from agents.telegram_bot import SYSTEM_TOOL_POLICY

# Simple in-memory history for demo purposes (Single User)
CONVERSATION_HISTORY = []

# Import tool wrappers
from tool_wrappers import (
    tool_get_wallet_balance,
    tool_transfer_tokens,
    tool_get_token_price,
    tool_check_address_security
)

# Initialize AI Client (OpenAI Compatible - e.g. DashScope)
ai_client = None
if Config.AI_API_KEY:
    try:
        from openai import AsyncOpenAI
        ai_client = AsyncOpenAI(
            api_key=Config.AI_API_KEY,
            base_url=Config.AI_API_BASE
        )
        print(f"🤖 AI Client Initialized: {Config.AI_PROVIDER} ({Config.AI_MODEL})")
    except ImportError:
        print("⚠️ openai package not found. Install with `pip install openai`")
        ai_client = None

app = FastAPI(title="BlockChain Copilot API")

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    message: str
    wallet_address: Optional[str] = None
    network: str = "nile"  # Default to Nile testnet

# --- Tool Definitions (OpenAI Format) ---

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_wallet_balance",
            "description": "Get the balance and portfolio of a TRON wallet address. Returns TRX and TRC20 token balances with USD value.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The TRON wallet address (starting with T) to check."
                    }
                },
                "required": ["address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_token_price",
            "description": "Get the current price of a cryptocurrency token in the TRON ecosystem.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "The token symbol (e.g., 'TRX', 'USDT', 'BTT'). Defaults to 'TRX'."
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_address_security",
            "description": "Check the security risk level of a TRON address. specific used for detect fraud, scam, or malicious activity.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The TRON address to check."
                    }
                },
                "required": ["address"]
            }
        }
    },
    # === 转账工作流专用 Skills ===
    {
        "type": "function",
        "function": {
            "name": "record_transfer",
            "description": "Step 1 of transfer workflow: Record this transfer in the address book. Looks up recipient alias and increments transfer count.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_address": {
                        "type": "string",
                        "description": "The recipient's TRON address to record."
                    }
                },
                "required": ["to_address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "check_malicious",
            "description": "Step 2 of transfer workflow: Check if address is flagged as malicious on TronScan blacklist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "address": {
                        "type": "string",
                        "description": "The TRON address to check for malicious tags."
                    }
                },
                "required": ["address"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "calculate_energy",
            "description": "Step 3 of transfer workflow (TRC20 only): Calculate energy required and rental cost for the transfer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "token": {
                        "type": "string",
                        "description": "Token symbol (USDT, TRX, etc.)"
                    }
                },
                "required": ["token"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "build_transfer",
            "description": "Step 4 of transfer workflow: Build the final unsigned transaction for TRX or TRC20 transfer.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_address": {
                        "type": "string",
                        "description": "The recipient's TRON address."
                    },
                    "token": {
                        "type": "string",
                        "description": "The token symbol to transfer (e.g., 'TRX', 'USDT')."
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount of tokens to transfer."
                    }
                },
                "required": ["to_address", "token", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "analyze_error",
            "description": "Analyze blockchain/transaction errors. Use when a transfer fails to explain why and suggest solutions.",
            "parameters": {
                "type": "object",
                "properties": {
                    "error_message": {
                        "type": "string",
                        "description": "The error message to analyze."
                    }
                },
                "required": ["error_message"]
            }
        }
    },
    # 保留旧的 transfer_tokens 作为快捷方式（内部调用上述 skills）
    {
        "type": "function",
        "function": {
            "name": "transfer_tokens",
            "description": "Quick transfer (combines all steps). Use the individual skills (record_transfer, check_malicious, calculate_energy, build_transfer) for step-by-step execution with explanations.",
            "parameters": {
                "type": "object",
                "properties": {
                    "to_address": {
                        "type": "string",
                        "description": "The recipient's TRON address."
                    },
                    "token": {
                        "type": "string",
                        "description": "The token symbol to transfer (e.g., 'TRX', 'USDT'). If user says 'u', use 'USDT'."
                    },
                    "amount": {
                        "type": "number",
                        "description": "The amount of tokens to transfer."
                    },
                    "memo": {
                        "type": "string",
                        "description": "Optional memo/note for the transfer. Also saved as address alias in address book. Example: if user says '备注小儿', memo should be '小儿'."
                    }
                },
                "required": ["to_address", "token", "amount"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_skill",
            "description": "Manage generated skills. Use this to explicitly 'save' (keep) or 'delete' (discard) a skill after testing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to manage (e.g., 'batch-transfer')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["save", "delete"],
                        "description": "Action to perform: 'save' to permanently keep it, 'delete' to remove it."
                    }
                },
                "required": ["skill_name", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_skill",
            "description": "Manage generated skills. Use this to explicitly 'save' (keep) or 'delete' (discard) a skill after testing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to manage (e.g., 'batch-transfer')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["save", "delete"],
                        "description": "Action to perform: 'save' to permanently keep it, 'delete' to remove it."
                    }
                },
                "required": ["skill_name", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_skill",
            "description": "Manage generated skills. Use this to explicitly 'save' (keep) or 'delete' (discard) a skill after testing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to manage (e.g., 'batch-transfer')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["save", "delete"],
                        "description": "Action to perform: 'save' to permanently keep it, 'delete' to remove it."
                    }
                },
                "required": ["skill_name", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_skill",
            "description": "Manage generated skills. Use this to explicitly 'save' (keep) or 'delete' (discard) a skill after testing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to manage (e.g., 'batch-transfer')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["save", "delete"],
                        "description": "Action to perform: 'save' to permanently keep it, 'delete' to remove it."
                    }
                },
                "required": ["skill_name", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_skill",
            "description": "Manage generated skills. Use this to explicitly 'save' (keep) or 'delete' (discard) a skill after testing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to manage (e.g., 'batch-transfer')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["save", "delete"],
                        "description": "Action to perform: 'save' to permanently keep it, 'delete' to remove it."
                    }
                },
                "required": ["skill_name", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_skill",
            "description": "Manage generated skills. Use this to explicitly 'save' (keep) or 'delete' (discard) a skill after testing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to manage (e.g., 'batch-transfer')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["save", "delete"],
                        "description": "Action to perform: 'save' to permanently keep it, 'delete' to remove it."
                    }
                },
                "required": ["skill_name", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_skill",
            "description": "Manage generated skills. Use this to explicitly 'save' (keep) or 'delete' (discard) a skill after testing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to manage (e.g., 'batch-transfer')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["save", "delete"],
                        "description": "Action to perform: 'save' to permanently keep it, 'delete' to remove it."
                    }
                },
                "required": ["skill_name", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "manage_skill",
            "description": "Manage generated skills. Use this to explicitly 'save' (keep) or 'delete' (discard) a skill after testing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "skill_name": {
                        "type": "string",
                        "description": "The name of the skill to manage (e.g., 'batch-transfer')."
                    },
                    "action": {
                        "type": "string",
                        "enum": ["save", "delete"],
                        "description": "Action to perform: 'save' to permanently keep it, 'delete' to remove it."
                    }
                },
                "required": ["skill_name", "action"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_skill",
            "description": "Generate a NEW skill when user asks for functionality NOT covered by existing tools. Example: 'Batch transfer', 'Wallet summary', 'DeFi analytics'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "requirement": {
                        "type": "string",
                        "description": "User's requirement description (e.g., 'Make a tool to batch transfer TRX')."
                    },
                    "skill_name": {
                        "type": "string",
                        "description": "Suggested name for the skill (e.g., 'batch-transfer', 'wallet-summary')."
                    }
                },
                "required": ["requirement", "skill_name"]
            }
        }
    }
]

# --- Tool Compatibility (Telegram + Frontend) ---

def _format_tools_for_openai(tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    formatted: List[Dict[str, Any]] = []
    for tool in tools:
        if "type" in tool and "function" in tool:
            formatted.append(tool)
            continue
        formatted.append(
            {
                "type": "function",
                "function": {
                    "name": tool.get("name"),
                    "description": tool.get("description", ""),
                    "parameters": tool.get("inputSchema", {}) or {},
                },
            }
        )
    return formatted


def get_llm_tools() -> List[Dict[str, Any]]:
    return _format_tools_for_openai(tron_tools.list_tools()["tools"])


def _normalize_tool_args(
    tool_name: str,
    tool_args: Dict[str, Any],
    user_wallet: Optional[str],
    network: str,
) -> Dict[str, Any]:
    args = dict(tool_args or {})
    if tool_name in {"transfer_tokens", "build_transfer"}:
        if user_wallet and not args.get("from_address"):
            args["from_address"] = user_wallet
        args.setdefault("network", network)
    if tool_name in {"check_malicious", "calculate_energy"}:
        args.setdefault("network", network)
    if tool_name == "get_wallet_balance" and user_wallet and not args.get("address"):
        args["address"] = user_wallet
    return args


# === Dynamic Skill Loading ===
def load_personal_skills() -> List[Dict]:
    """Load skills dynamically from personal-skills directory."""
    skills = []
    import sys
    from pathlib import Path
    
    # Use parent-parent to get out of src/ and into project root
    skills_dir = Path(__file__).resolve().parent.parent / "personal-skills"
    
    if not skills_dir.exists():
        return []
        
    for skill_path in skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
            
        # Try to load metadata
        metadata_file = skill_path / "metadata.json"
        
        # Determine name and description
        skill_name = skill_path.name
        description = f"User generated skill: {skill_name}"
        
        if metadata_file.exists():
            try:
                import json
                with open(metadata_file, 'r') as f:
                    meta = json.load(f)
                    skill_name = meta.get('name', skill_name)
                    description = meta.get('description', description)
            except:
                pass
        
        # Determine parameters (Simplified for demo)
        parameters = {"type": "object", "properties": {}, "required": []}
        
        if skill_name == "batch_transfer":
            parameters = {
                "type": "object",
                "properties": {
                    "recipients": {"type": "string", "description": "JSON string of recipients"},
                    "token": {"type": "string", "description": "Token symbol"}
                },
                "required": ["recipients", "token"]
            }
        elif skill_name == "wallet_summary":
            parameters = {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Wallet address"}
                },
                "required": []
            }
        else:
            # Generic catch-all
            parameters = {
                "type": "object",
                "properties": {
                    "kwargs": {"type": "string", "description": "Arguments for the skill as JSON string"}
                }
            }
            
        skills.append({
            "type": "function",
            "function": {
                "name": skill_name,
                "description": description,
                "parameters": parameters
            }
        })
        
    return skills

def get_all_tools() -> List[Dict]:
    """Get core tools + dynamically loaded tools."""
    return TOOLS + load_personal_skills()

# === Dynamic Skill Loading ===
def load_personal_skills() -> List[Dict]:
    """Load skills dynamically from personal-skills directory."""
    skills = []
    import sys
    from pathlib import Path
    
    # Use parent-parent to get out of src/ and into project root
    skills_dir = Path(__file__).resolve().parent.parent / "personal-skills"
    
    if not skills_dir.exists():
        return []
        
    for skill_path in skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
            
        # Try to load metadata
        metadata_file = skill_path / "metadata.json"
        skill_file = skill_path / "SKILL.md"
        
        # Determine name and description
        skill_name = skill_path.name
        description = f"User generated skill: {skill_name}"
        
        if metadata_file.exists():
            try:
                import json
                with open(metadata_file, 'r') as f:
                    meta = json.load(f)
                    skill_name = meta.get('name', skill_name)
                    description = meta.get('description', description)
            except:
                pass
        
        # Determine parameters (Simplified for demo)
        parameters = {"type": "object", "properties": {}, "required": []}
        
        if skill_name == "batch_transfer":
            parameters = {
                "type": "object",
                "properties": {
                    "recipients": {"type": "string", "description": "JSON string of recipients"},
                    "token": {"type": "string", "description": "Token symbol"}
                },
                "required": ["recipients", "token"]
            }
        elif skill_name == "wallet_summary":
            parameters = {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Wallet address"}
                },
                "required": []
            }
        else:
            # Generic catch-all
            parameters = {
                "type": "object",
                "properties": {
                    "kwargs": {"type": "string", "description": "Arguments for the skill as JSON string"}
                }
            }
            
        skills.append({
            "type": "function",
            "function": {
                "name": skill_name,
                "description": description,
                "parameters": parameters
            }
        })
        
    return skills

def get_all_tools() -> List[Dict]:
    """Get core tools + dynamically loaded tools."""
    return TOOLS + load_personal_skills()

# === Dynamic Skill Loading ===
def load_personal_skills() -> List[Dict]:
    """Load skills dynamically from personal-skills directory."""
    skills = []
    skills_dir = Path(__file__).resolve().parent.parent / "personal-skills"
    
    if not skills_dir.exists():
        return []
        
    for skill_path in skills_dir.iterdir():
        if not skill_path.is_dir():
            continue
            
        # Try to load metadata
        metadata_file = skill_path / "metadata.json"
        skill_file = skill_path / "SKILL.md"
        
        # Determine name and description
        skill_name = skill_path.name
        description = f"User generated skill: {skill_name}"
        
        if metadata_file.exists():
            try:
                import json
                with open(metadata_file, 'r') as f:
                    meta = json.load(f)
                    skill_name = meta.get('name', skill_name)
                    description = meta.get('description', description)
            except:
                pass
        elif skill_file.exists():
            # Try to parse from SKILL.md
            pass
            
        # Create tool definition
        # Note: This is a simplified definition. Ideally we should parse args from python file.
        # For this demo, we assume a generic 'args' parameter or specific ones if we know them.
        
        # For batch_transfer and wallet_summary demo, we hardcode their signatures if detected
        parameters = {"type": "object", "properties": {}, "required": []}
        
        if skill_name == "batch_transfer":
            parameters = {
                "type": "object",
                "properties": {
                    "recipients": {"type": "string", "description": "JSON string of recipients"},
                    "token": {"type": "string", "description": "Token symbol"}
                },
                "required": ["recipients", "token"]
            }
        elif skill_name == "wallet_summary":
            parameters = {
                "type": "object",
                "properties": {
                    "address": {"type": "string", "description": "Wallet address"}
                },
                "required": []
            }
        else:
            # Generic catch-all
            parameters = {
                "type": "object",
                "properties": {
                    "kwargs": {"type": "string", "description": "Arguments for the skill as JSON string"}
                }
            }
            
        skills.append({
            "type": "function",
            "function": {
                "name": skill_name,
                "description": description,
                "parameters": parameters
            }
        })
        
    return skills

def get_all_tools() -> List[Dict]:
    """Get core tools + dynamically loaded tools."""
    return TOOLS + load_personal_skills()

async def execute_tool(tool_name: str, tool_args: Dict[str, Any], user_wallet: Optional[str], network: str = "nile") -> str:
    """Execute the tool requested by the LLM."""
    print(f"🔧 Tool Call: {tool_name} with args {tool_args} on network {network}")
    try:
        args = _normalize_tool_args(tool_name, tool_args, user_wallet, network)
        result = await asyncio.to_thread(tron_tools.call_tool, tool_name, args)
        if isinstance(result, (dict, list)):
            return json.dumps(result, ensure_ascii=False)
        if result is None:
            return "✅ Done"
        return str(result)
    except Exception as e:
        return f"❌ Tool Execution Error: {str(e)}"

# --- Fallback Logic ---

def get_fallback_response(message: str, wallet_address: Optional[str] = None) -> str:
    """Fallback response when AI is unavailable."""
    return "💡 AI Service Unavailable. Please check your API Key configuration."

# --- Main Endpoint ---

# --- Energy Rental Endpoint ---

class EnergyRentalRequest(BaseModel):
    """Request to rent energy for a transaction."""
    transaction: dict
    recipient_address: str
    network: str
    estimated_energy: int


class EnergyRentalResponse(BaseModel):
    """Response from energy rental service."""
    success: bool
    mode: str  # "simulated", "rented", "failed"
    message: str
    energy_amount: int
    cost_sun: Optional[int] = None
    cost_trx: Optional[float] = None
    savings_percentage: Optional[float] = None
    rental_txid: Optional[str] = None


@app.post("/api/rent-energy", response_model=EnergyRentalResponse)
async def rent_energy(request: EnergyRentalRequest) -> EnergyRentalResponse:
    """
    Rent energy for a TRON transaction.
    
    - Testnet: Returns simulation with educational information
    - Mainnet: Attempts real energy rental (future implementation)
    """
    
    print(f"[Energy Rental] Request: network={request.network}, energy={request.estimated_energy}")
    
    # Testnet mode: Simulate rental
    if request.network in ["nile", "shasta"]:
        print("[Energy Rental] Testnet mode: Simulating energy rental")
        
        # Calculate what it would cost on mainnet
        # Approximate: 1 TRX = 1,000,000 SUN
        # Energy price on mainnet: ~40-60 SUN per energy
        # Using 50 SUN as average
        estimated_cost_sun = request.estimated_energy * 50
        estimated_cost_trx = estimated_cost_sun / 1_000_000
        
        # Compare to burning TRX (280 SUN per energy)
        burn_cost_sun = request.estimated_energy * 280
        burn_cost_trx = burn_cost_sun / 1_000_000
        
        # Calculate savings
        savings_sun = burn_cost_sun - estimated_cost_sun
        savings_trx = burn_cost_trx - estimated_cost_trx
        savings_percentage = (savings_sun / burn_cost_sun) * 100 if burn_cost_sun > 0 else 0
        
        return EnergyRentalResponse(
            success=True,
            mode="simulated",
            message=(
                f"💡 Testnet simulation: On mainnet, renting {request.estimated_energy:,} energy "
                f"would cost ~{estimated_cost_trx:.2f} TRX and save ~{savings_trx:.2f} TRX "
                f"({savings_percentage:.0f}% savings) compared to burning TRX. "
                f"Proceeding with normal transaction on testnet."
            ),
            energy_amount=request.estimated_energy,
            cost_sun=estimated_cost_sun,
            cost_trx=estimated_cost_trx,
            savings_percentage=savings_percentage
        )
    
    # Mainnet mode: Real rental (to be implemented)
    elif request.network == "mainnet":
        print("[Energy Rental] Mainnet energy rental not yet implemented")
        return EnergyRentalResponse(
            success=False,
            mode="failed",
            message="Mainnet energy rental coming soon! Please proceed with normal transaction.",
            energy_amount=request.estimated_energy
        )
    
    else:
        return EnergyRentalResponse(
            success=False,
            mode="failed",
            message=f"Unknown network: {request.network}",
            energy_amount=request.estimated_energy
        )

# --- Resource Query Endpoint ---

@app.get("/api/get-resources/{address}")
async def get_resources(address: str, network: str = "nile"):
    """
    Get account resources (staking status and available energy).
    
    Returns staked TRX amount, available energy, and calculations.
    """
    from tronpy import Tron
    
    print(f"[Resource Query] Address: {address[:6]}...{address[-6:]}, Network: {network}")
    
    # Select network
    network_endpoints = {
        'mainnet': 'https://api.trongrid.io',
        'nile': 'https://nile.trongrid.io',
        'shasta': 'https://api.shasta.trongrid.io'
    }
    
    full_node = network_endpoints.get(network, network_endpoints['nile'])
    
    try:
        client = Tron(network=full_node)
        account = client.get_account(address)
        
        # Parse account data
        total_trx = account.get('balance', 0) /1_000_000  # Convert from SUN to TRX
        
        # Get frozen balance (Stake 2.0)
        frozen_v2 = account.get('frozenV2', [])
        staked_for_energy = 0
        staked_for_bandwidth = 0
        
        for frozen in frozen_v2:
            if frozen.get('type') == 'ENERGY':
                staked_for_energy += frozen.get('amount', 0) / 1_000_000
            elif frozen.get('type') == 'BANDWIDTH':
                staked_for_bandwidth += frozen.get('amount', 0) / 1_000_000
        
        # Get energy info
        account_resource = account.get('account_resource', {})
        energy_limit = account_resource.get('energy_limit', 0)
        energy_used = account_resource.get('energy_used', 0)
        energy_remaining = max(0, energy_limit - energy_used)
        
        # Get bandwidth info
        net_limit = account.get('net_limit', 0) + account.get('free_net_limit', 0)
        net_used = account.get('net_used', 0) + account.get('free_net_used', 0)
        bandwidth_remaining = max(0, net_limit - net_used)
        
        return {
            "address": address,
            "balance": {
                "total_trx": total_trx,
                "staked_for_energy": staked_for_energy,
                "staked_for_bandwidth": staked_for_bandwidth,
                "liquid_trx": total_trx  # Note: staked TRX is still counted in balance
            },
            "energy": {
                "total": energy_limit,
                "used": energy_used,
                "remaining": energy_remaining,
                "percentage_used": (energy_used / energy_limit * 100) if energy_limit > 0 else 0
            },
            "bandwidth": {
                "total": net_limit,
                "used": net_used,
                "remaining": bandwidth_remaining,
                "percentage_used": (net_used / net_limit * 100) if net_limit > 0 else 0
            },
            "calculations": {
                "energy_per_trx": 357,
                "bandwidth_per_trx": 1000,
                "estimated_transactions_remaining": energy_remaining // 28000  # Approximate for USDT transfers
            }
        }
        
    except Exception as e:
        print(f"[ERROR] Failed to get resources: {e}")
        return {
            "error": str(e),
            "address": address
        }


@app.get("/api/tools")
async def list_tools():
    """Return available tool names and descriptions for the frontend."""
    items = tron_tools.list_tools().get("tools", [])
    tools = [
        {
            "name": tool.get("name"),
            "description": tool.get("description", ""),
        }
        for tool in items
        if tool.get("name")
    ]
    return {"tools": tools}

# --- Error Analysis Endpoint ---

class ErrorAnalysisRequest(BaseModel):
    error_message: str
    error_context: Optional[str] = None  # e.g., "transfer", "signing", "broadcast"
    transaction_details: Optional[dict] = None

class ErrorAnalysisResponse(BaseModel):
    analysis: str
    possible_causes: List[str]
    suggestions: List[str]

@app.post("/api/analyze-error", response_model=ErrorAnalysisResponse)
async def analyze_error(request: ErrorAnalysisRequest):
    """
    Analyze transaction/blockchain errors using LLM.
    
    Provides user-friendly explanations of technical errors.
    """
    print(f"[Error Analysis] Analyzing error: {request.error_message[:100]}...")
    
    if not ai_client:
        # Fallback without AI
        return ErrorAnalysisResponse(
            analysis="发生了错误，但无法分析原因（AI未配置）",
            possible_causes=["技术错误"],
            suggestions=["请检查网络连接", "稍后重试"]
        )
    
    try:
        # Prepare context for LLM
        context_parts = [f"错误信息：{request.error_message}"]
        if request.error_context:
            context_parts.append(f"错误场景：{request.error_context}")
        if request.transaction_details:
            context_parts.append(f"交易详情：{json.dumps(request.transaction_details, indent=2)}")
        
        full_context = "\n".join(context_parts)
        
        # Ask LLM to analyze
        response = await ai_client.chat.completions.create(
            model=Config.AI_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": """你是TRON专家。用户遇到错误，提供超简洁分析。

要求：
- 总字数 < 100
- 直接说原因，不重复错误信息
- 2个主要原因
- 2个解决方案

格式：
原因：[一句话]
1. [原因1]
2. [原因2]
建议：
1. [方案1]
2. [方案2]

常见错误：
- balance not sufficient = TRX不足
- Contract validate = 能量/带宽不足
- account not found = 账户未激活"""
                },
                {
                    "role": "user",
                    "content": f"请分析这个TRON交易错误并给出建议：\n\n{full_context}"
                }
            ],
            temperature=0.3,
            max_tokens=500
        )
        
        analysis_text = response.choices[0].message.content or "无法分析错误"
        
        # Parse response (simple extraction)
        lines = analysis_text.split('\n')
        causes = []
        suggestions = []
        
        in_causes = False
        in_suggestions = False
        
        for line in lines:
            line = line.strip()
            if '可能原因' in line or '原因' in line:
                in_causes = True
                in_suggestions = False
                continue
            elif '建议' in line or '解决' in line:
                in_causes = False
                in_suggestions = True
                continue
            
            if line and (line.startswith('-') or line.startswith('•') or line.startswith(str(len(causes)+1)) or line.startswith(str(len(suggestions)+1))):
                clean_line = line.lstrip('-•0123456789. ')
                if in_causes and clean_line:
                    causes.append(clean_line)
                elif in_suggestions and clean_line:
                    suggestions.append(clean_line)
        
        # Fallback if parsing failed
        if not causes:
            causes = ["交易执行失败", "可能是网络或合约问题"]
        if not suggestions:
            suggestions = ["检查钱包余额", "稍后重试"]
        
        return ErrorAnalysisResponse(
            analysis=analysis_text,
            possible_causes=causes[:3],
            suggestions=suggestions[:3]
        )
        
    except Exception as e:
        print(f"[ERROR] Error analysis failed: {e}")
        return ErrorAnalysisResponse(
            analysis=f"错误分析失败：{str(e)}",
            possible_causes=["分析服务异常"],
            suggestions=["请手动检查错误信息", "联系技术支持"]
        )

def get_personal_skills_tools():
    """Dynamically load tool definitions from personal-skills directory."""
    personal_tools = []
    personal_skills_dir = Path(__file__).resolve().parent.parent / "personal-skills"
    
    if personal_skills_dir.exists():
        for skill_dir in personal_skills_dir.iterdir():
            if skill_dir.is_dir():
                skill_json_path = skill_dir / "skill.json"
                if skill_json_path.exists():
                    try:
                        with open(skill_json_path, 'r', encoding='utf-8') as f:
                            tool_def = json.load(f)
                            personal_tools.append(tool_def)
                            print(f"📦 Loaded dynamic tool: {tool_def['function']['name']}")
                    except Exception as e:
                        print(f"⚠️ Failed to load skill.json from {skill_dir.name}: {e}")
    return personal_tools

# --- Chat Endpoint ---
# ...

@app.post("/chat")
async def chat(request: ChatRequest):
    """
    Chat endpoint - OpenAI Function Calling Loop
    """
    global CONVERSATION_HISTORY
    
    # Check for clear command
    if request.message.strip().lower() in ["clear", "reset", "清除", "重置"]:
        CONVERSATION_HISTORY = []
        return PlainTextResponse("🧹 Memory cleared. Context reset.")

    async def generate_response() -> str:
        # If no AI client, use fallback
        if not ai_client:
            return get_fallback_response(request.message, request.wallet_address)

        system_prompt = f"""{SYSTEM_TOOL_POLICY}

You are TRON Copilot, an expert AI assistant for the TRON blockchain.
Connected User Wallet: {request.wallet_address if request.wallet_address else 'Not Connected'}

Your goal is to help users manage assets, check prices, and stay safe.
Use the available tools to answer user questions.

## Tools Usage

- **查询余额**: use `get_wallet_balance`
- **查询价格**: use `get_token_price`
- **安全检查**: use `check_address_security`
- **转账**: use `transfer_tokens` - 会自动执行以下 skill 链:
  1. 📇 address-book - 查询/记录地址
  2. 🚨 malicious-detector - 检测恶意地址
  3. 🔒 risk-checker - 风险评估
  4. ⚡ energy-rental - 能量计算 (TRC20)
  5. 🔨 build-transfer - 构建交易

- **新功能生成**: 对未知需求，**优先**调用 `custom_tools_write` 创建工具，然后调用 `custom_tools_reload` 热加载，再使用新工具。若已有同名工具存在，先调用它。

## 重要规则

1. **语言一致性**: 用户说中文你就用中文回复
2. **Markdown 链接**: URL 必须用 Markdown 格式 `[标题](URL)`
3. **转账UI**: transfer_tokens 返回交易后，下方会自动出现签名卡片
4. **展示 Skill 结果**: 如果 tool 返回了 "Skill 链执行结果" 区块，你必须**原样输出该区块**到聊天中，不要总结或省略。
5. **USDT**: 用户说 'u' 或 'U' 表示 USDT

如果不知道答案，直接说不知道。"""

        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(CONVERSATION_HISTORY[-10:])
        messages.append({"role": "user", "content": request.message})

        try:
            all_tools = get_llm_tools()
            response = await ai_client.chat.completions.create(
                model=Config.AI_MODEL,
                messages=messages,
                tools=all_tools,
                tool_choice="auto",
                stream=False,
            )
            choice = response.choices[0].message
            full_content = choice.content or ""
            tool_calls = choice.tool_calls or []

            if tool_calls:
                assistant_msg = {
                    "role": "assistant",
                    "content": full_content if full_content else None,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name or "",
                                "arguments": tc.function.arguments or "",
                            },
                        }
                        for tc in tool_calls
                    ],
                }
                messages.append(assistant_msg)

                output_chunks = []
                tool_json_blocks = []
                output_chunks.append("\n\n---\n\n")
                output_chunks.append("🔧 **正在执行 Skills**：\n\n")

                for tc in tool_calls:
                    fn_name = tc.function.name or ""
                    fn_args_str = tc.function.arguments or "{}"
                    try:
                        fn_args = json.loads(fn_args_str)
                    except json.JSONDecodeError:
                        fn_args = {}

                    if fn_name == "transfer_tokens":
                        to_address = fn_args.get("to_address", "")
                        token = fn_args.get("token", "TRX")
                        amount = fn_args.get("amount", 0)

                        output_chunks.append("📇 **Step 1/5 - 地址簿查询**\n")
                        step_result = await execute_tool(
                            "record_transfer",
                            {"to_address": to_address},
                            request.wallet_address,
                            request.network,
                        )
                        output_chunks.append(f"{step_result}\n\n")

                        output_chunks.append("🚨 **Step 2/5 - 恶意地址检测**\n")
                        step_result = await execute_tool(
                            "check_malicious",
                            {"address": to_address, "network": request.network},
                            request.wallet_address,
                            request.network,
                        )
                        output_chunks.append(f"{step_result}\n\n")

                        output_chunks.append("🔒 **Step 3/5 - 安全风险评估**\n")
                        step_result = await execute_tool(
                            "check_address_security",
                            {"address": to_address},
                            request.wallet_address,
                            request.network,
                        )
                        output_chunks.append(f"{step_result}\n\n")

                        output_chunks.append("⚡ **Step 4/5 - 能量计算**\n")
                        step_result = await execute_tool(
                            "calculate_energy",
                            {"token": token, "network": request.network},
                            request.wallet_address,
                            request.network,
                        )
                        output_chunks.append(f"{step_result}\n\n")

                        output_chunks.append("🔨 **Step 5/5 - 构建交易**\n")
                        result_str = await execute_tool(
                            "build_transfer",
                            {
                                "to_address": to_address,
                                "token": token,
                                "amount": amount,
                                "memo": fn_args.get("memo", ""),
                                "network": request.network,
                            },
                            request.wallet_address,
                            request.network,
                        )
                        if "❌" in result_str or "Error" in result_str:
                            output_chunks.append("   ❌ 构建失败\n\n")
                        else:
                            output_chunks.append("   ✅ 交易已生成，等待签名\n\n")
                        output_chunks.append("---\n\n")
                    else:
                        tool_descriptions = {
                            "get_token_price": "查询代币价格",
                            "get_wallet_balance": "获取钱包余额",
                            "check_address_security": "检查地址安全性",
                        }
                        desc = tool_descriptions.get(fn_name, fn_name)
                        output_chunks.append(f"• {desc} (`{fn_name}`)\n")
                        result_str = await execute_tool(
                            fn_name,
                            fn_args,
                            request.wallet_address,
                            request.network,
                        )
                        if result_str:
                            output_chunks.append(f"{result_str}\n\n")

                    import re
                    json_pattern = r'<<<JSON\s*(.*?)\s*JSON>>>'
                    matches = re.findall(json_pattern, result_str or "", re.DOTALL)
                    if matches:
                        for json_content in matches:
                            tool_json_blocks.append(f"<<<JSON\n{json_content}\nJSON>>>")

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": result_str or "",
                        }
                    )

                second_response = await ai_client.chat.completions.create(
                    model=Config.AI_MODEL,
                    messages=messages,
                    stream=False,
                )
                final_content = second_response.choices[0].message.content or ""

                CONVERSATION_HISTORY.append({"role": "user", "content": request.message})
                CONVERSATION_HISTORY.append(assistant_msg)
                for msg in messages:
                    if msg.get("role") == "tool":
                        CONVERSATION_HISTORY.append(msg)
                CONVERSATION_HISTORY.append({"role": "assistant", "content": final_content})

                output = "".join(output_chunks) + final_content
                if tool_json_blocks:
                    output += "\n\n" + "\n\n".join(tool_json_blocks)
                return output

            CONVERSATION_HISTORY.append({"role": "user", "content": request.message})
            CONVERSATION_HISTORY.append({"role": "assistant", "content": full_content})
            return full_content

        except Exception as e:
            print(f"Agent Loop Error: {e}")
            return f"❌ AI Error: {str(e)}"

    return PlainTextResponse(await generate_response())
    return PlainTextResponse(await generate_response())



@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "message": "Server is running (Agent Mode - OpenAI)",
        "ai_enabled": ai_client is not None,
        "model": Config.AI_MODEL
    }

@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "name": "BlockChain Copilot API",
        "version": "3.1-Agent-OpenAI",
        "features": ["chat", "agent_tools"],
        "endpoints": {
            "chat": "/chat",
            "health": "/health"
        }
    }

if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting BlockChain Copilot API Server...")
    print(f"🤖 Mode: Agent with {Config.AI_PROVIDER} ({Config.AI_MODEL})")
    print("🌐 Frontend: http://localhost:3000")
    print("🔧 API: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
