from mcp.server.fastmcp import FastMCP
from skills_loader import SkillsLoader
from tool_wrappers import (
    tool_get_token_price,
    tool_get_wallet_balance,
    tool_swap_tokens,
    tool_energy_rental,
    tool_transfer_tokens,
    tool_check_address_security,
    tool_list_contacts,
    tool_search_contacts,
    tool_profile_address
)

# Initialize FastMCP server
mcp = FastMCP("BlockChain-Copilot")

# Initialize Skills Loader (scans both system and personal skills)
skills_loader = SkillsLoader("skills", "personal-skills")

# Discover available skills on startup
print("🔍 Discovering Agent Skills...")
discovered_skills = skills_loader.discover_skills()
print(f"✅ Found {len(discovered_skills)} skills:")
for skill in discovered_skills:
    skill_type = "🎨" if skill.get('skill_type') == 'personal' else "⚙️"
    generated_mark = " [AI-Generated]" if skill.get('generated') else ""
    desc = skill['description'][:60] if skill.get('description') else "No description"
    print(f"   {skill_type} {skill['name']}: {desc}...{generated_mark}")


# Register MCP Tools
# The tools are wrappers around skill scripts, with human-readable output

@mcp.tool()
async def get_token_price(symbol: str) -> str:
    """Get real-time cryptocurrency price for TRON ecosystem tokens."""
    return await tool_get_token_price(symbol)

@mcp.tool()
async def get_wallet_balance(address: str) -> str:
    """Get comprehensive portfolio view of TRON wallet with USD valuations."""
    return await tool_get_wallet_balance(address)

@mcp.tool()
async def swap_tokens(
    user_address: str,
    token_in: str,
    token_out: str,
    amount_in: float,
    slippage: float = 0.5
) -> str:
    """Build unsigned transaction for token swap on SunSwap DEX."""
    return await tool_swap_tokens(user_address, token_in, token_out, amount_in, slippage)

@mcp.tool()
async def energy_rental(energy_needed: int, duration_days: int = 3) -> str:
    """Analyze energy costs and get rental proposals to save on transaction fees."""
    return await tool_energy_rental(energy_needed, duration_days)

@mcp.tool()
async def transfer_tokens(
    from_address: str,
    to_address: str,
    token: str,
    amount: float,
    memo: str = ""
) -> str:
    """Build unsigned transaction for transferring TRX or TRC20 tokens to another address."""
    return await tool_transfer_tokens(from_address, to_address, token, amount, memo)
@mcp.tool()
async def check_address_security(address: str) -> str:
    """Check if a TRON address is safe using TronScan security database (blacklist, fraud detection, labels)."""
    return await tool_check_address_security(address)

@mcp.tool()
async def list_contacts(sort_by: str = "count") -> str:
    """List address book contacts. sort_by: 'count' (most used), 'recent', or 'alpha'."""
    return await tool_list_contacts(sort_by)

@mcp.tool()
async def search_contacts(query: str) -> str:
    """Search address book by alias or address."""
    return await tool_search_contacts(query)

@mcp.tool()
async def profile_address(address_or_alias: str, max_transactions: int = 1000) -> str:
    """Analyze address behavior patterns from transaction history. Supports alias from address book."""
    return await tool_profile_address(address_or_alias, max_transactions)

if __name__ == "__main__":
    print("🚀 Starting BlockChain-Copilot MCP Server...")
    print(f"📦 {len(discovered_skills)} skills loaded and ready")
    mcp.run()
