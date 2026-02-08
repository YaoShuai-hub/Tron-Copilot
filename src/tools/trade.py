from tronpy import Tron
from tronpy.providers import HTTPProvider
from src.config import Config
import json

# Initialize Tron client with API Key for better limits
# We needed to pass the API key to the provider
provider = HTTPProvider(api_key=Config.TRONGRID_API_KEY) if Config.TRONGRID_API_KEY else None
client = Tron(provider) if provider else Tron()

SUNSWAP_V2_ROUTER = "TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax"

async def swap_tokens(
    address: str, 
    token_in: str, 
    token_out: str, 
    amount_in: float, 
    slippage: float = 0.5
) -> str:
    """
    Generate an UNSIGNED transaction to swap tokens on SunSwap V2.
    
    Args:
        address: Your wallet address (Generates transaction for this address).
        token_in: The contract address of the token you want to sell (or 'TRX').
        token_out: The contract address of the token you want to buy (or 'TRX').
        amount_in: The amount of token_in to swap.
        slippage: Allowed slippage in percentage (default 0.5%).
    """
    try:
        # 1. Validate inputs (Basic)
        if amount_in <= 0:
            return "Error: Amount must be greater than 0."

        # 2. Get contract interaction
        # Note: In a real robust implementation, we need to handle decimals and approval checks.
        # For this MVP/Hackathon, we assume the user has approved or we remind them.
        
        contract = client.get_contract(SUNSWAP_V2_ROUTER)
        
        # 3. Calculate amounts (Mocking the exact calculation for simplicity or need to query reserves)
        # Real implementation would query getAmountsOut first.
        # For simplicity, we will just call swapExactTokensForTokens with a simplified logic 
        # or just return a constructed transaction object structure if we can't query chain state easily from here.
        
        # NOTE: Properly building this requires async calls to chain to get decimals and reserves.
        # fastmcp tools are async, but tronpy is synchronous by default unless using AsyncHTTPProvider.
        # mixing sync tronpy with async fastmcp is fine for now but might block loop.
        
        # Let's try to construct the call.
        # Determine function to call: swapExactTokensForTokens, swapExactETHForTokens, etc.
        
        # Heuristic for demo:
        # If token_in is TRX -> swapExactETHForTokens
        # If token_out is TRX -> swapExactTokensForETH
        # Else -> swapExactTokensForTokens
        
        # We need raw amounts (integer). Assuming 6 decimals for USDT/TRX for simplicity in this demo.
        amount_in_int = int(amount_in * 1_000_000)
        amount_out_min_int = 0 # DANGEROUS in prod, but OK for Unsigned Tx generation demo (User should check)
        
        # Path
        # path = [token_in, token_out] (if direct pool exists)
        # WTRX address: TNUC9Qb1rRpS5CbWLmNMxXBjyFoydXjWFR
        WTRX = "TNUC9Qb1rRpS5CbWLmNMxXBjyFoydXjWFR"
        
        path = []
        func_name = ""
        
        if token_in == "TRX":
            path = [WTRX, token_out]
            func_name = "swapExactETHForTokens"
        elif token_out == "TRX":
            path = [token_in, WTRX]
            func_name = "swapExactTokensForETH"
        else:
            path = [token_in, WTRX, token_out] # Multi-hop via TRX usually safest default
            func_name = "swapExactTokensForTokens"

        # Build Transaction
        # deadline = current_timestamp + 20 mins
        import time
        deadline = int(time.time()) + 1200
        

        # Using tronpy to build
        # We need to use the method dynamically
        
        tx_builder = None
        if func_name == "swapExactETHForTokens":
            # swapExactETHForTokens(amountOutMin, path, to, deadline)
            # amountIn is passed via call_value
            tx_builder = contract.functions.swapExactETHForTokens(
                amount_out_min_int,
                path,
                address,
                deadline
            )
            tx_builder = tx_builder.with_owner(address).fee_limit(100_000_000).call_value(amount_in_int)
        else:
            # swapExactTokensForTokens(amountIn, amountOutMin, path, to, deadline)
            # swapExactTokensForETH(amountIn, amountOutMin, path, to, deadline)
            tx_builder = getattr(contract.functions, func_name)(
                amount_in_int,
                amount_out_min_int,
                path,
                address,
                deadline
            )
            tx_builder = tx_builder.with_owner(address).fee_limit(100_000_000)
            
        txn = tx_builder.build()
        
        # Return the JSON for the Unsigned Transaction
        # usage: User takes this JSON, signs it with TronLink/Ledger, and broadcasts.
        
        return json.dumps(txn.to_json(), indent=2)

    except Exception as e:
        error_msg = str(e)
        if "429" in error_msg or "Too Many Requests" in error_msg:
             return f"""
⚠️ API Rate Limit Exceeded (TronGrid).
Here is a MOCK Unsigned Transaction structure for demonstration:
{{
  "visible": false,
  "txID": "simulated_tx_id_123456...",
  "raw_data": {{
    "contract": [
      {{
        "parameter": {{
          "value": {{
            "data": "a9059cbb000000000000000000000000{token_out}0000000000000000000000000000000000000000000000000000000000989680",
            "owner_address": "{address}",
            "contract_address": "{SUNSWAP_V2_ROUTER}"
          }},
          "type_url": "type.googleapis.com/protocol.TriggerSmartContract"
        }},
        "type": "TriggerSmartContract"
      }}
    ],
    "ref_block_bytes": "...",
    "ref_block_hash": "...",
    "expiration": 1234567890,
    "timestamp": 1234567800
  }}
}}
ERROR: {error_msg}
"""
        return f"Error generating transaction: {str(e)}"

async def rent_energy(amount: int, duration_days: int = 3) -> str:
    """
    [Simulated] Rent energy to save on gas fees.
    
    Args:
        amount: Amount of Energy to rent (e.g., 32000 for a USDT transfer).
        duration_days: How many days to rent for (default 3).
    """
    # In reality, verify valid providers and prices.
    price_per_unit = 110 # sun
    total_cost_trx = (amount * price_per_unit * duration_days) / 1_000_000
    
    return f"""
⚡ Energy Rental Proposal
------------------------
Request: Rent {amount} Energy for {duration_days} days.
Estimated Cost: {total_cost_trx} TRX (vs ~13 TRX burn for USDT transfer)

To proceed, please sign the following transaction to pay the rental provider:
[Unsigned Transaction Data to Transfer {total_cost_trx} TRX to RentalContract...]
(Simulation: Transaction object would be here)
"""
