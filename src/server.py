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
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from config import Config

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
        if tool_name == "get_wallet_balance":
            address = tool_args.get("address") or user_wallet
            if not address:
                return "❌ Error: No wallet address provided and user is not connected."
            return await tool_get_wallet_balance(address, network=network)

        elif tool_name == "get_token_price":
            symbol = tool_args.get("symbol", "TRX")
            return await tool_get_token_price(symbol)

        elif tool_name == "check_address_security":
            address = tool_args.get("address")
            if not address:
                 return "❌ Error: No address provided for check."
            return await tool_check_address_security(address, network=network)
        
        # === 转账工作流 Skills ===
        elif tool_name == "record_transfer":
            # Step 1: Record transfer in address book
            to_address = tool_args.get("to_address")
            if not to_address:
                return "❌ Error: No recipient address provided."
            
            # Import and call the function
            import sys
            from pathlib import Path
            skill_path = Path(__file__).resolve().parent.parent / "skills" / "address-book" / "scripts"
            sys.path.insert(0, str(skill_path))
            from manage_contacts import get_contact_alias, save_contact
            
            alias = get_contact_alias(to_address)
            contact_info = save_contact(to_address, alias=alias, increment_count=True)
            transfer_count = contact_info.get('transfer_count', 1)
            
            if alias:
                return f"""📇 **地址簿记录**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 找到已保存联系人: **{alias}**
📊 历史转账次数: **第 {transfer_count} 次**

→ 已知地址，安全性较高"""
            else:
                return f"""📇 **地址簿记录**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️ 新地址，首次转账
📊 已添加到地址簿

💡 提示: 使用 `/save-contact {to_address[:8]}... <名称>` 可以添加别名"""
        
        elif tool_name == "check_malicious":
            # Step 2: Check malicious address
            address = tool_args.get("address")
            if not address:
                return "❌ Error: No address provided."
            
            try:
                import sys
                from pathlib import Path
                skill_path = Path(__file__).resolve().parent.parent / "skills" / "malicious-address-detector" / "scripts"
                sys.path.insert(0, str(skill_path))
                from check_malicious import check_malicious_address
                result = await check_malicious_address(address, network)
            except ImportError:
                # Fallback if skill not available
                result = {"is_malicious": False, "risk_level": "UNKNOWN", "warnings": ["Skill not available"]}
            
            if result.get('is_malicious'):
                return f"""🚨 **恶意地址检测**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
❌ **危险: 此地址已被标记为恶意地址!**

⚠️ 标签: {', '.join(result.get('tags', ['Scam']))}
⚠️ 警告: {result.get('warnings', ['请勿向此地址转账'])[0]}

🛑 **强烈建议取消此次转账!**"""
            elif result.get('risk_level') == 'WARNING':
                return f"""🚨 **恶意地址检测**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
⚠️ 需要注意: {result.get('warnings', [''])[0]}

→ 建议谨慎操作"""
            else:
                return f"""🚨 **恶意地址检测**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✅ 未发现恶意标签
📊 数据来源: TronScan

→ 可以继续下一步"""
        
        elif tool_name == "calculate_energy":
            # Step 3: Calculate energy (TRC20 only)
            token = tool_args.get("token", "TRX")
            
            if token.upper() == "TRX":
                return f"""⚡ **能量计算**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ℹ️ TRX 转账不需要能量，只需带宽
📊 预计消耗: ~270 带宽

→ 无需租赁能量，可以直接转账"""
            
            # TRC20 needs energy
            try:
                import sys
                from pathlib import Path
                skill_path = Path(__file__).resolve().parent.parent / "skills" / "energy-rental" / "scripts"
                sys.path.insert(0, str(skill_path))
                from calculate_rental import get_rental_proposal
                result = await get_rental_proposal(28000, 1, network)
                
                if 'error' in result:
                    return f"⚠️ 能量计算失败: {result['error']}"
                
                burn_cost = result.get('burn_cost_trx', 0)
                rec = result.get('recommendation', {})
                action = rec.get('action', 'unknown')
                
                output = f"""⚡ **能量计算** ({token.upper()})
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 预计消耗: ~28,000 能量

💰 成本对比:
  燃烧 TRX: {burn_cost:.2f} TRX"""
                
                if result.get('rental_options'):
                    best = result['rental_options'][0]
                    output += f"""
  租赁能量: {best['cost_trx']:.2f} TRX (节省 {best['savings_percent']:.0f}%)

💡 建议: **{action.upper()}**"""
                
                return output
                
            except ImportError:
                return f"""⚡ **能量计算**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 {token.upper()} 转账需要约 28,000 能量
💰 预计消耗: ~3 TRX

→ 能量计算模块不可用，使用默认估算"""
        
        elif tool_name == "build_transfer":
            # Step 4: Build the actual transfer
            if not user_wallet:
                return "⚠️ 请先连接钱包才能进行转账"
            
            return await tool_transfer_tokens(
                from_address=user_wallet,
                to_address=tool_args["to_address"],
                token=tool_args.get("token", "TRX"),
                amount=float(tool_args["amount"]),
                network=network
            )
        
        elif tool_name == "analyze_error":
            # Analyze blockchain errors
            error_msg = tool_args.get("error_message", "")
            
            try:
                import sys
                from pathlib import Path
                skill_path = Path(__file__).resolve().parent.parent / "skills" / "error-analysis" / "scripts"
                sys.path.insert(0, str(skill_path))
                from analyze_error import analyze_error as ae
                result = await ae(error_msg)
                return f"""🔧 **错误分析**
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{result.get('analysis', '无法分析错误')}

💡 建议:
{chr(10).join(f'  {i+1}. {s}' for i, s in enumerate(result.get('suggestions', [])))}"""
            except Exception as e:
                return f"⚠️ 错误分析失败: {str(e)}"

        elif tool_name == "transfer_tokens":
            # For transfer, we rely on the LLM to extract to_address from the message
            # The 'from_address' is the connected user_wallet
            if not user_wallet:
                return "⚠️ Please connect your wallet first to perform transfers."
            
            return await tool_transfer_tokens(
                from_address=user_wallet,
                to_address=tool_args["to_address"],
                token=tool_args.get("token", "TRX"),
                amount=float(tool_args["amount"]),
                network=network
            )
        
        # === Skill Generator ===
        elif tool_name == "generate_skill":
            requirement = tool_args.get("requirement", "")
            skill_name = tool_args.get("skill_name", "").lower().replace(" ", "-")
            
            # Use the real skill generator module
            try:
                import sys
                from pathlib import Path
                
                # Import generator module dynamically
                generator_path = Path(__file__).resolve().parent.parent / "skills" / "skill-generator" / "scripts"
                sys.path.insert(0, str(generator_path))
                import generator
                
                # 1. Analyze requirement (Mocking existing skills list for now)
                analysis = await generator.analyze_requirement(requirement, [])
                
                # Override suggested name if provided by LLM
                final_skill_name = skill_name if skill_name else analysis['suggested_name']
                
                # 2. Generate Plan
                plan = await generator.generate_skill_plan(requirement, final_skill_name, [])
                
                # 3. Generate Code (This will now load from templates if available)
                generated_code = await generator.generate_skill_code(plan, requirement)
                
                # 4. Save Skill
                save_result = generator.save_generated_skill(generated_code)
                
                if save_result['success']:
                    return f"""✅ **新技能生成成功！** (Powered by Skill Generator)

🛠️ **技能名称**: `{final_skill_name}`
📂 **位置**: `{save_result['skill_dir']}`

此技能已自动部署。请告诉我您想执行的操作（例如："{requirement}"），我会使用新生成的技能来完成。"""
                else:
                    return f"❌ 保存技能失败: {save_result.get('error', 'Unknown error')}"

            except Exception as e:
                return f"❌ 生成技能失败: {str(e)}\n\nDebug Info: Ensure skills/skill-generator is correctly configured."""
        
        elif tool_name == "manage_skill":
            skill_name = tool_args.get("skill_name")
            action = tool_args.get("action")
            
            import shutil
            from pathlib import Path
            base_dir = Path(__file__).resolve().parent.parent / "personal-skills" / skill_name
            
            if action == 'delete':
                if base_dir.exists():
                    shutil.rmtree(base_dir)
                    return f"🗑️ 技能 '{skill_name}' 已删除。"
                else:
                    return f"⚠️ 技能 '{skill_name}' 不存在。"
            elif action == 'save':
                if base_dir.exists():
                    return f"💾 技能 '{skill_name}' 已确认保存到个人技能库。"
                else:
                    return f"⚠️ 技能 '{skill_name}' 不存在，无法保存。"

        # === Dynamic Skill Execution ===
        else:
            # Check if it is a dynamically loaded personal skill
            import sys
            import importlib.util
            from pathlib import Path
            
            skill_dir = Path(__file__).resolve().parent.parent / "personal-skills" / tool_name
            
            if not (skill_dir.exists() and (skill_dir / "scripts" / "main.py").exists()):
                 return f"❌ Error: Unknown tool '{tool_name}'"

            # Retry Loop for Self-Correction
            max_retries = 1
            attempt = 0
            
            while attempt <= max_retries:
                attempt += 1
                
                try:
                    # 1. Load Module
                    sys.path.insert(0, str(skill_dir / "scripts"))
                    if tool_name in sys.modules:
                         del sys.modules[tool_name] # Force reload
                    
                    # Dynamic import
                    spec = importlib.util.spec_from_file_location("dynamic_skill", skill_dir / "scripts" / "main.py")
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[f"personal_skill_{tool_name}"] = module
                    spec.loader.exec_module(module)
                    
                    if not hasattr(module, 'execute_skill'):
                        return f"❌ Error: Skill '{tool_name}' has no execute_skill function."

                    # 2. Map Arguments
                    # Map args based on tool name (simplified mapping for demo)
                    call_args = {}
                    # 2. Map Arguments
                    call_args = {}
                    if tool_name == "batch_transfer":
                        # Support both direct list and JSON string
                        recipients = tool_args.get("recipients", [])
                        if isinstance(recipients, str):
                            try:
                                recipients = json.loads(recipients)
                            except:
                                pass
                        
                        call_args = {
                            "from_address": user_wallet,
                            "recipients": recipients,
                            "token": tool_args.get("token", "TRX"),
                            "network": network,
                            **tool_args
                        }
                    elif tool_name == "wallet_summary":
                        call_args = {
                            "address": tool_args.get("address") or user_wallet,
                            "network": network
                        }
                    else:
                        call_args = tool_args
                        
                    # 3. Execute
                    print(f"🔧 [Dynamic Skill] Executing '{tool_name}' (Attempt {attempt})...")
                    result = await module.execute_skill(**call_args)
                    
                    # Format output based on result
                    output_msg = str(result)
                    if isinstance(result, dict):
                        if result.get('success'):
                             output_msg = result.get('message', '✅ Success')
                        else:
                             # If success=False, treat as error for retry/repair
                             raise Exception(result.get('message', result.get('error', 'Unknown error')))
                    
                    return output_msg

                except Exception as e:
                    error_msg = str(e)
                    print(f"❌ [Dynamic Skill] Attempt {attempt} failed: {error_msg}")
                    
                    if attempt > max_retries:
                         return f"❌ Error executing dynamic skill '{tool_name}': {error_msg}"
                    
                    # Attempt Self-Correction
                    print(f"⚠️ Attempting to fix skill '{tool_name}' with AI...")
                    try:
                        code_path = skill_dir / "scripts" / "main.py"
                        code = code_path.read_text(encoding='utf-8')
                        
                        from skills.skill_generator.scripts import generator
                        if ai_client:
                            refine_result = await generator.refine_skill(
                                skill_name=tool_name,
                                error=error_msg,
                                code=code,
                                client=ai_client
                            )
                            
                            if refine_result['success']:
                                print(f"✅ Skill fixed! Retrying...")
                                continue # Retry loop
                    except Exception as fix_err:
                        print(f"❌ Self-correction failed: {fix_err}")
                    
                    return f"❌ 执行并尝试修复失败: {error_msg}"

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
        async def clear_gen():
             yield "🧹 Memory cleared. Context reset."
        return StreamingResponse(clear_gen(), media_type="text/plain")

    async def generate():
        # If no AI client, use fallback
        if not ai_client:
             fallback = get_fallback_response(request.message, request.wallet_address)
             for char in fallback:
                yield char
                await asyncio.sleep(0.01)
             return

        # Prepare available tools
        # We need to filter tools if certain conditions aren't met? No, LLM decides.
        
        system_prompt = f"""You are TRON Copilot, an expert AI assistant for the TRON blockchain.
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

- **新功能生成**: 如果用户请求的功能（如批量转账、钱包概览、DeFi分析）没在上述列表里，**你必须**调用 `generate_skill` 来创建该功能。不要尝试手动分步执行。

## 重要规则

1. **语言一致性**: 用户说中文你就用中文回复
2. **Markdown 链接**: URL 必须用 Markdown 格式 `[标题](URL)`
3. **转账UI**: transfer_tokens 返回交易后，下方会自动出现签名卡片
4. **展示 Skill 结果**: 如果 tool 返回了 "Skill 链执行结果" 区块，你必须**原样输出该区块**到聊天中，不要总结或省略。
5. **USDT**: 用户说 'u' 或 'U' 表示 USDT

如果不知道答案，直接说不知道。"""

        # Construct messages with history
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(CONVERSATION_HISTORY[-10:])
        messages.append({"role": "user", "content": request.message})

        try:
            # Prepare tools including dynamic personal skills
            all_tools = TOOLS + get_personal_skills_tools()
            
            # 1. First API Call: Send User Message + Tools
            response = await ai_client.chat.completions.create(
                model=Config.AI_MODEL,
                messages=messages,
                tools=all_tools,
                tool_choice="auto",
                stream=True
            )

            # Accumulate stream for tool calls or text
            full_content = ""
            tool_calls = []
            current_tool_call = None

            async for chunk in response:
                delta = chunk.choices[0].delta
                
                # Check for content
                if delta.content:
                    content_chunk = delta.content
                    full_content += content_chunk
                    # Yield text immediately if no tool calls expected yet
                    if not tool_calls and not current_tool_call:
                         yield content_chunk
                         await asyncio.sleep(0.005)

                # Check for tool calls
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        # Logic to handle new vs existing tool call chunks
                        if tc.id:
                            # If we have a current tool call and the ID is different, flush the current one
                            if current_tool_call and tc.id != current_tool_call["id"]:
                                tool_calls.append(current_tool_call)
                                current_tool_call = None
                            
                            # If no current tool call (or we just flushed), create new
                            if not current_tool_call:
                                current_tool_call = {
                                    "id": tc.id,
                                    "function": {
                                        "name": tc.function.name or "",
                                        "arguments": ""
                                    }
                                }
                        
                        # Update name if present (and we have a current tool call)
                        if tc.function.name and current_tool_call:
                             if not current_tool_call["function"]["name"]:
                                 current_tool_call["function"]["name"] = tc.function.name

                        # Update arguments
                        if tc.function.arguments and current_tool_call:
                            current_tool_call["function"]["arguments"] += tc.function.arguments

            # Finish last tool call
            if current_tool_call:
                tool_calls.append(current_tool_call)
            
            # If we had tool calls, execute them
            if tool_calls:
                # Add the assistant's request to valid messages logic? 
                # OpenAI requires the message with tool_calls to be in history
                # But since we streamed, we need to reconstruct the message object
                assistant_msg = {
                    "role": "assistant",
                    "content": full_content if full_content else None,
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": tc["function"]
                        } for tc in tool_calls
                    ]
                }
                messages.append(assistant_msg)

                # Execute tools
                tool_json_blocks = []  # Store JSON blocks to yield after LLM response
                
                # Display skill calls to user
                if len(tool_calls) > 0:
                    yield "\n\n---\n\n"
                    yield "🔧 **正在执行 Skills**：\n\n"
                
                for tc in tool_calls:
                    fn_name = tc["function"]["name"]
                    fn_args_str = tc["function"]["arguments"]
                    
                    try:
                        fn_args = json.loads(fn_args_str)
                    except json.JSONDecodeError:
                         fn_args = {}
                    
                    # Special handling for transfer_tokens: stream each sub-skill result
                    if fn_name == "transfer_tokens":
                        to_address = fn_args.get("to_address", "")
                        token = fn_args.get("token", "TRX")
                        amount = fn_args.get("amount", 0)
                        
                        # Step 1: Address Book
                        yield "📇 **Step 1/5 - 地址簿查询**\n"
                        try:
                            from skills.address_book.scripts.manage_contacts import get_contact_alias, save_contact
                        except ImportError:
                            import sys
                            from pathlib import Path
                            skill_path = Path(__file__).resolve().parent.parent / "skills" / "address-book" / "scripts"
                            sys.path.insert(0, str(skill_path))
                            from manage_contacts import get_contact_alias, save_contact
                        
                        # Get memo from args (user-provided note)
                        memo = fn_args.get("memo", "").strip()
                        existing_alias = get_contact_alias(to_address)
                        
                        # If user provided memo, use it as new alias
                        if memo:
                            save_contact(to_address, alias=memo, increment_count=True)
                            if existing_alias and existing_alias != memo:
                                yield f"   ✅ 已更新联系人: **{existing_alias}** → **{memo}**\n\n"
                            else:
                                yield f"   ✅ 已保存联系人别名: **{memo}**\n\n"
                        elif existing_alias:
                            save_contact(to_address, alias=existing_alias, increment_count=True)
                            yield f"   ✅ 已知联系人: **{existing_alias}**\n\n"
                        else:
                            save_contact(to_address, alias=None, increment_count=True)
                            yield f"   ℹ️ 新地址，已添加到通讯录\n\n"
                        await asyncio.sleep(0.1)
                        
                        # Step 2: Malicious Check
                        yield "🚨 **Step 2/5 - 恶意地址检测**\n"
                        try:
                            import sys
                            from pathlib import Path
                            skill_path = Path(__file__).resolve().parent.parent / "skills" / "malicious-address-detector" / "scripts"
                            sys.path.insert(0, str(skill_path))
                            from check_malicious import check_malicious_address
                            malicious_result = await check_malicious_address(to_address, request.network)
                            if malicious_result.get('is_malicious'):
                                yield f"   🛑 **危险！此地址已被标记为恶意地址**\n"
                                yield f"   ⚠️ 建议：放弃此次转账\n\n"
                            else:
                                yield f"   ✅ 未发现恶意标签\n\n"
                        except Exception as e:
                            yield f"   ⚠️ 检测跳过: {str(e)[:50]}\n\n"
                        await asyncio.sleep(0.1)
                        
                        # Step 3: Risk Check
                        yield "🔒 **Step 3/5 - 安全风险评估**\n"
                        try:
                            from tool_wrappers import check_address_security
                            risk_result = await check_address_security(to_address)
                            risk_level = risk_result.get('risk_level', 'UNKNOWN')
                            if risk_level in ['SAFE', 'LOW']:
                                yield f"   ✅ 风险评估: {risk_level}\n\n"
                            elif risk_level == 'HIGH':
                                yield f"   ⚠️ 高风险地址，请谨慎操作\n\n"
                            else:
                                yield f"   ℹ️ 风险级别: {risk_level}\n\n"
                        except Exception as e:
                            yield f"   ⚠️ 评估跳过: {str(e)[:50]}\n\n"
                        await asyncio.sleep(0.1)
                        
                        # Step 4: Energy Calculation (TRC20 only)
                        if token.upper() != 'TRX':
                            yield "⚡ **Step 4/5 - 能量计算**\n"
                            yield f"   📊 {token.upper()} 转账预计需要 ~28,000 能量\n"
                            yield f"   💡 建议使用能量租赁节省费用\n\n"
                            await asyncio.sleep(0.1)
                        else:
                            yield "⚡ **Step 4/5 - 资源检查**\n"
                            yield f"   ✅ TRX 转账仅需带宽，无需能量\n\n"
                            await asyncio.sleep(0.1)
                        
                        # Step 5: Build Transaction
                        yield "🔨 **Step 5/5 - 构建交易**\n"
                        result_str = await execute_tool(fn_name, fn_args, request.wallet_address, request.network)
                        
                        # Check for error
                        if "❌" in result_str or "Error" in result_str:
                            yield f"   ❌ 构建失败\n\n"
                        else:
                            yield f"   ✅ 交易已生成，等待签名\n\n"
                        
                        yield "---\n\n"
                    else:
                        # Normal tool execution
                        tool_descriptions = {
                            "get_token_price": "查询代币价格",
                            "get_wallet_balance": "获取钱包余额",
                            "check_address_security": "检查地址安全性",
                        }
                        desc = tool_descriptions.get(fn_name, fn_name)
                        yield f"• {desc} (`{fn_name}`)\n"
                        result_str = await execute_tool(fn_name, fn_args, request.wallet_address, request.network)
                    
                    # Extract JSON blocks (<<<JSON...JSON>>>) from result
                    import re
                    json_pattern = r'<<<JSON\s*(.*?)\s*JSON>>>'
                    matches = re.findall(json_pattern, result_str, re.DOTALL)
                    if matches:
                        for json_content in matches:
                            tool_json_blocks.append(f"<<<JSON\n{json_content}\nJSON>>>")
                    
                    # Add result to messages
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": result_str
                    })

                # 2. Second API Call: Send Tool Results -> Valid Response
                second_response = await ai_client.chat.completions.create(
                    model=Config.AI_MODEL,
                    messages=messages,
                    stream=True
                )

                # First, stream the LLM's natural language response
                full_final_content = ""
                async for chunk in second_response:
                    if chunk.choices[0].delta.content:
                        content = chunk.choices[0].delta.content
                        full_final_content += content
                        yield content
                        await asyncio.sleep(0.005)

                # Record History (Complex interaction)
                CONVERSATION_HISTORY.append({"role": "user", "content": request.message})
                # Note: assistant_msg (tool calls) was created earlier
                CONVERSATION_HISTORY.append(assistant_msg) 
                
                # Append tool outputs from messages list
                for msg in messages:
                    if msg.get("role") == "tool":
                        CONVERSATION_HISTORY.append(msg)
                        
                CONVERSATION_HISTORY.append({"role": "assistant", "content": full_final_content})
                
                # Then, append the JSON blocks at the end
                for json_block in tool_json_blocks:
                    yield "\n\n" + json_block
            
            # 3. No Tool Calls Case
            if not tool_calls:
                 CONVERSATION_HISTORY.append({"role": "user", "content": request.message})
                 CONVERSATION_HISTORY.append({"role": "assistant", "content": full_content})

        except Exception as e:
            print(f"Agent Loop Error: {e}")
            yield f"❌ AI Error: {str(e)}"
    
    return StreamingResponse(generate(), media_type="text/plain")


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
