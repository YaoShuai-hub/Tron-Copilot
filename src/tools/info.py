from mcp.server.fastmcp import FastMCP
from src.tron_client import TronClient

# We need to reference the mcp object. 
# In FastMCP, it's common to pass the mcp object or have it global.
# Since we are importing this into main, we can define functions here and register them in main,
# OR we can pass the mcp object here to register.
# Let's define pure async functions and register them in main.py for better separation.

async def get_token_price(symbol: str) -> str:
    """
    Get the current price of a token in USD.
    
    Args:
        symbol: The token symbol (e.g., TRX, USDT, BTT).
    """
    client = TronClient()
    try:
        price = await client.get_token_price(symbol)
        await client.close()
        return f"The current price of {symbol.upper()} is ${price} USD."
    except Exception as e:
        await client.close()
        return f"Error fetching price for {symbol}: {str(e)}"

async def get_token_security(token_address: str) -> str:
    """
    [Simulated] Check the security status of a token contract.
    
    Args:
        token_address: The TRON contract address of the token.
    """
    # In a real app, this would call GoPlus Security API or TronScan contract verification info
    # For MVP, we'll return a mock "Safe" or "Risky" based on address length or known list
    
    known_safe = [
        "TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t", # USDT
        "TN3W4H6rK2ce4vX9YnFQHwKENnHjoxb3m9", # BTTC
        "TssMHYimnStBujWN5frYRHuf1sc2For37q"  # SunSwap V2
    ]
    
    if token_address in known_safe:
        return f"Security Scan for {token_address}:\n✅ Status: SAFE\n- Verified Contract: Yes\n- High Trust Score"
    else:
        return f"Security Scan for {token_address}:\n⚠️ Status: UNKNOWN/CAUTION\n- Contract might be unverified.\n- Please DYOR (Do Your Own Research) before trading."
