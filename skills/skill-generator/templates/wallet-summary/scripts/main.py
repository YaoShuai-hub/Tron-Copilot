"""
Wallet Summary - Generated skill
Purpose: Get comprehensive wallet overview including all token balances
"""
import asyncio
import httpx
from typing import Dict, Optional
from pathlib import Path
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import Config

async def execute_skill(
    address: str,
    network: str = "nile"
) -> Dict:
    """
    Get comprehensive wallet summary.
    
    Args:
        address: TRON wallet address
        network: Network (mainnet/nile)
        
    Returns:
        Dict with wallet summary
    """
    try:
        # Determine API base
        if network == "mainnet":
            api_base = "https://api.trongrid.io"
        else:
            api_base = "https://nile.trongrid.io"
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Get account info
            response = await client.get(
                f"{api_base}/v1/accounts/{address}"
            )
            
            if response.status_code != 200:
                return {
                    'success': False,
                    'error': f"API error: {response.status_code}",
                    'message': 'Failed to fetch account info'
                }
            
            data = response.json()
            
            if not data.get('data') or len(data['data']) == 0:
                return {
                    'success': True,
                    'message': 'Account not found or inactive',
                    'data': {
                        'address': address,
                        'network': network,
                        'trx_balance': 0,
                        'tokens': [],
                        'is_active': False
                    }
                }
            
            account = data['data'][0]
            
            # Parse balances
            trx_balance = account.get('balance', 0) / 1_000_000  # Convert SUN to TRX
            
            # Parse TRC20 tokens
            tokens = []
            trc20 = account.get('trc20', [])
            for token_info in trc20:
                for contract, amount in token_info.items():
                    tokens.append({
                        'contract': contract,
                        'balance': int(amount)
                    })
            
            # Get bandwidth and energy
            bandwidth = account.get('net_window_size', 0)
            energy = account.get('account_resource', {}).get('energy_window_size', 0)
            
            return {
                'success': True,
                'message': 'Wallet summary retrieved',
                'data': {
                    'address': address,
                    'network': network,
                    'trx_balance': trx_balance,
                    'tokens': tokens,
                    'bandwidth': bandwidth,
                    'energy': energy,
                    'is_active': True
                }
            }
            
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to get wallet summary: {str(e)}'
        }
