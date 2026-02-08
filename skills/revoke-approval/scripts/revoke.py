"""
Revoke Approval Skill
Revoke risky token approvals to protect wallet security.
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

TRONGRID_BASE = Config.TRONGRID_BASE

async def build_revoke_transaction(
    owner_address: str,
    token_address: str,
    spender_address: str
) -> Dict:
    """
    Build an unsigned transaction to revoke token approval.
    
    This sets the allowance to 0, preventing the spender contract
    from accessing the owner's tokens.
    
    Args:
        owner_address: Wallet address that granted approval
        token_address: TRC20 token contract address
        spender_address: Contract address to revoke approval from
        
    Returns:
        Dict with unsigned transaction and metadata
    """
    try:
        # Validate addresses
        if not all([owner_address, token_address, spender_address]):
            return {
                'success': False,
                'error': 'Missing required addresses',
                'message': 'Please provide owner, token, and spender addresses'
            }
        
        # Get token info
        token_info = await _get_token_info(token_address)
        
        # Check current allowance
        current_allowance = await _get_allowance(
            token_address, owner_address, spender_address
        )
        
        if current_allowance == 0:
            return {
                'success': False,
                'error': 'NoApprovalFound',
                'message': f'No approval found for {spender_address} on {token_info.get("symbol", "this token")}'
            }
        
        # Build revoke transaction (approve with amount = 0)
        unsigned_tx = await _build_approve_tx(
            owner_address=owner_address,
            token_address=token_address,
            spender_address=spender_address,
            amount=0  # 0 = revoke
        )
        
        return {
            'success': True,
            'message': 'Revoke approval transaction created successfully',
            'data': {
                'owner': owner_address,
                'token': token_address,
                'token_symbol': token_info.get('symbol', 'Unknown'),
                'token_name': token_info.get('name', 'Unknown'),
                'spender': spender_address,
                'old_allowance': str(current_allowance),
                'new_allowance': '0',
                'unsigned_tx': unsigned_tx,
                'estimated_energy': 15000,
                'estimated_bandwidth': 345
            },
            'warnings': [
                f"⚠️ This will prevent {spender_address[:10]}... from spending your {token_info.get('symbol', 'tokens')}",
                "You'll need to re-approve if you want to use this contract again"
            ],
            'next_steps': [
                "1. Review the transaction details",
                "2. Sign the transaction in your wallet (e.g., TronLink)",
                "3. Broadcast to network",
                "4. Wait for confirmation (~3 seconds)",
                "5. Approval revoked ✅"
            ]
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to build revoke transaction: {str(e)}'
        }


async def batch_revoke_approvals(
    owner_address: str,
    approvals_to_revoke: list
) -> Dict:
    """
    Build multiple revoke transactions.
    
    Args:
        owner_address: Wallet address
        approvals_to_revoke: List of dicts with 'token_address' and 'spender'
        
    Returns:
        Dict with all unsigned transactions
    """
    results = []
    
    for approval in approvals_to_revoke:
        tx = await build_revoke_transaction(
            owner_address=owner_address,
            token_address=approval['token_address'],
            spender_address=approval['spender']
        )
        results.append(tx)
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.3)
    
    successful = sum(1 for r in results if r['success'])
    
    return {
        'success': True,
        'message': f'Generated {successful}/{len(approvals_to_revoke)} revoke transactions',
        'data': {
            'total_approvals': len(approvals_to_revoke),
            'successful': successful,
            'failed': len(approvals_to_revoke) - successful,
            'transactions': results
        }
    }


async def _get_token_info(token_address: str) -> Dict:
    """Get token name and symbol."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Try to get token info from TronScan
            response = await client.get(
                f"https://apilist.tronscanapi.com/api/token_trc20",
                params={'contract': token_address}
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('trc20_tokens'):
                    token = data['trc20_tokens'][0]
                    return {
                        'symbol': token.get('symbol', 'Unknown'),
                        'name': token.get('name', 'Unknown'),
                        'decimals': token.get('decimals', 6)
                    }
    except:
        pass
    
    return {'symbol': 'Unknown', 'name': 'Unknown', 'decimals': 6}


async def _get_allowance(
    token_address: str,
    owner_address: str,
    spender_address: str
) -> int:
    """
    Get current allowance amount.
    Calls TRC20 allowance(owner, spender) function.
    """
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Build allowance function call
            # Function signature: allowance(address,address)
            response = await client.post(
                f"{TRONGRID_BASE}/wallet/triggerconstantcontract",
                json={
                    "owner_address": owner_address,
                    "contract_address": token_address,
                    "function_selector": "allowance(address,address)",
                    "parameter": _encode_allowance_params(owner_address, spender_address),
                    "visible": True
                }
            )
            
            if response.status_code == 200:
                data = response.json()
                if data.get('constant_result'):
                    # Decode uint256 result
                    allowance_hex = data['constant_result'][0]
                    allowance = int(allowance_hex, 16)
                    return allowance
    except Exception as e:
        print(f"Error getting allowance: {e}")
    
    return 0


async def _build_approve_tx(
    owner_address: str,
    token_address: str,
    spender_address: str,
    amount: int
) -> Dict:
    """
    Build approve transaction.
    For revoke, amount = 0.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{TRONGRID_BASE}/wallet/triggersmartcontract",
            json={
                "owner_address": owner_address,
                "contract_address": token_address,
                "function_selector": "approve(address,uint256)",
                "parameter": _encode_approve_params(spender_address, amount),
                "fee_limit": 15000000,  # 15 TRX max
                "call_value": 0,
                "visible": True
            }
        )
        
        if response.status_code == 200:
            data = response.json()
            if 'transaction' in data:
                return data['transaction']
        
        raise Exception(f"Failed to build transaction: {response.text}")


def _encode_allowance_params(owner: str, spender: str) -> str:
    """
    Encode parameters for allowance(address,address) call.
    """
    # Remove 'T' prefix and convert to hex (simplified version)
    # In production, use tronpy for proper encoding
    from tronpy.keys import to_base58check_address
    
    owner_hex = owner[1:].lower()  # Remove 'T'
    spender_hex = spender[1:].lower()
    
    # Pad to 32 bytes each
    param = owner_hex.zfill(64) + spender_hex.zfill(64)
    return param


def _encode_approve_params(spender: str, amount: int) -> str:
    """
    Encode parameters for approve(address,uint256) call.
    """
    # Remove 'T' prefix
    spender_hex = spender[1:].lower()
    
    # Convert amount to hex (32 bytes)
    amount_hex = hex(amount)[2:].zfill(64)
    
    # Combine: spender (32 bytes) + amount (32 bytes)
    param = spender_hex.zfill(64) + amount_hex
    return param


# For testing
if __name__ == "__main__":
    async def test():
        # Test revoking an approval
        result = await build_revoke_transaction(
            owner_address="TYourAddress...",
            token_address="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # USDT
            spender_address="TTestContract..."
        )
        
        print(result)
    
    asyncio.run(test())
