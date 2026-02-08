"""
Enhanced token swap transaction builder with validation and path finding.
"""
from tronpy import Tron
from tronpy.providers import HTTPProvider
from src.config import Config
import json
import time
from typing import Dict, List, Optional

# Known token addresses
TOKEN_ADDRESSES = {
    'USDT': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
    'USDD': 'TPYmHEhy5n8TCEfYGqW2rPxsghSfzghPDn',
    'WTRX': 'TNUC9Qb1rRpS5CbWLmNMxXBjyFoydXjWFR',
    'BTT': 'TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4',
    'JST': 'TCFLL5dx5ZJdKnWuesXxi1VPwjLVmWZZy9'
}

SUNSWAP_V2_ROUTER = "TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax"

# Initialize Tron client
provider = HTTPProvider(api_key=Config.TRONGRID_API_KEY) if Config.TRONGRID_API_KEY else None
tron_client = Tron(provider) if provider else Tron()

async def build_swap_transaction(
    user_address: str,
    token_in: str,
    token_out: str,
    amount_in: float,
    slippage: float = 0.5
) -> Dict:
    """
    Build an unsigned swap transaction for SunSwap V2.
    
    Args:
        user_address: Wallet address that will sign the transaction
        token_in: Input token (symbol or address, or "TRX")
        token_out: Output token (symbol or address, or "TRX")
        amount_in: Amount of input token
        slippage: Max slippage tolerance in percentage
        
    Returns:
        Dict with unsigned transaction and metadata
    """
    try:
        # Resolve token addresses
        token_in_addr = _resolve_token_address(token_in)
        token_out_addr = _resolve_token_address(token_out)
        
        # Validate amount
        if amount_in <= 0:
            return {'error': 'Amount must be greater than 0'}
        
        # Determine swap function and path
        is_trx_in = (token_in.upper() == 'TRX')
        is_trx_out = (token_out.upper() == 'TRX')
        
        if is_trx_in:
            func_name = 'swapExactETHForTokens'
            path = [TOKEN_ADDRESSES['WTRX'], token_out_addr]
        elif is_trx_out:
            func_name = 'swapExactTokensForETH'
            path = [token_in_addr, TOKEN_ADDRESSES['WTRX']]
        else:
            func_name = 'swapExactTokensForTokens'
            # Multi-hop through WTRX for most pairs
            path = [token_in_addr, TOKEN_ADDRESSES['WTRX'], token_out_addr]
        
        # Convert amount to integer (assuming 6 decimals for simplicity)
        # TODO: Fetch actual decimals from contract
        decimals = 6
        amount_in_int = int(amount_in * (10 ** decimals))
        
        # Calculate minimum output (with slippage)
        # TODO: Query actual reserves for expectation output
        amount_out_min_int = 0  # Placeholder - should calculate from reserves
        
        # Build deadline (20 minutes from now)
        deadline = int(time.time()) + 1200
        
        # Get contract
        contract = tron_client.get_contract(SUNSWAP_V2_ROUTER)
        
        # Build transaction based on function
        if func_name == 'swapExactETHForTokens':
            # For TRX input: swapExactETHForTokens(amountOutMin, path, to, deadline)
            tx_builder = contract.functions.swapExactETHForTokens(
                amount_out_min_int,
                path,
                user_address,
                deadline
            )
            tx_builder = tx_builder.with_owner(user_address).fee_limit(100_000_000).call_value(amount_in_int)
        else:
            # For token input: swapExactTokensFor...(amountIn, amountOutMin, path, to, deadline)
            tx_builder = getattr(contract.functions, func_name)(
                amount_in_int,
                amount_out_min_int,
                path,
                user_address,
                deadline
            )
            tx_builder = tx_builder.with_owner(user_address).fee_limit(100_000_000)
        
        # Build unsigned transaction
        txn = tx_builder.build()
        tx_json = txn.to_json()
        
        # Add metadata
        result = {
            'transaction': tx_json,
            'metadata': {
                'function': func_name,
                'path': path,
                'input_amount': amount_in,
                'slippage': slippage,
                'deadline': deadline,
                'estimated_output': 'Unknown (query reserves)',
                'instructions': [
                    '1. Review the transaction details',
                    '2. Ensure you have approved the input token (if not TRX)',
                    '3. Sign this transaction in your wallet',
                    '4. Broadcast to complete the swap'
                ]
            }
        }
        
        return result
        
    except Exception as e:
        # Rate limit fallback
        error_msg = str(e)
        if '429' in error_msg or '401' in error_msg:
            return {
                'error': 'API rate limit or auth error',
                'fallback': 'mock_transaction',
                'message': 'Add TRONGRID_API_KEY to config.toml for real transactions'
            }
        return {'error': str(e)}

def _resolve_token_address(token: str) -> str:
    """Resolve token symbol to address, or return address if already address."""
    if token.upper() in TOKEN_ADDRESSES:
        return TOKEN_ADDRESSES[token.upper()]
    # Check if it's already an address (starts with T, 34 chars)
    if token.startswith('T') and len(token) == 34:
        return token
    return token
