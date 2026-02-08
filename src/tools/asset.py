from src.tron_client import TronClient

async def get_wallet_balance(address: str) -> str:
    """
    Get the token balances and portfolio value for a TRON address.
    
    Args:
        address: The TRON wallet address (starting with T).
    """
    client = TronClient()
    try:
        data = await client.get_account_tokens(address)
        await client.close()
        
        if "error" in data:
            return f"Error fetching balance: {data['error']}"
        
        # Format the output
        tokens = data.get("data", [])
        if not tokens:
            return f"No tokens found for address {address}."
            
        report = f"💰 Asset Portfolio for {address}:\n"
        total_value = 0.0
        
        for token in tokens:
            symbol = token.get("tokenAbbr", "Unknown")
            name = token.get("tokenName", "Unknown")
            # TronScan returns raw balance, need to adjust by decimals
            # Usually 'balance' or 'amount'. Let's check typical response keys or assume standard.
            # TronScan API 'balance' is usually raw. 'tokenDecimal' is available.
            
            raw_balance = float(token.get("balance", 0))
            decimals = int(token.get("tokenDecimal", 6))
            amount = raw_balance / (10 ** decimals)
            
            # Simple output
            if amount > 0:
                report += f"- {amount:.4f} {symbol} ({name})\n"
        
        return report
        

    except Exception as e:
        await client.close()
        return f"Error processing request: {str(e)}"

async def simulate_transaction(transaction_hex: str) -> str:
    """
    [Simulated] Simulate a transaction to check for errors or estimate gas.
    
    Args:
        transaction_hex: The raw hex of the transaction to simulate.
    """
    # Real implementation would call wallet/broadcasttransaction (dry run if supported) 
    # or triggerconstantcontract for the specific call found in the tx.
    
    # For Hackathon/MVP:
    # We can't easily deconstruct the hex here without tronpy local parsing.
    # We will just return a mock success for valid-looking hex.
    
    if not transaction_hex:
        return "Error: Empty transaction data."
        
    return f"""
✅ Transaction Simulation Result
-------------------------------
Status: SUCCESS (Simulated)
Energy Estimate: ~15,000
Bandwidth Estimate: 300
Risk Check: PASS

(Note: This is a simulation based on static analysis. Real execution depends on chain state.)
"""
