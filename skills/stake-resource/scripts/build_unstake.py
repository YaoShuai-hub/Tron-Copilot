"""
Build Unstake (UnfreezeBalanceV2) transaction for TRON network

Allows users to unstake TRX and release locked resources.
"""

import sys
import json
from tronpy import Tron
from tronpy.keys import to_base58check_address

# Energy gain ratio (approximate)
ENERGY_PER_TRX = 357  # 1 TRX ≈ 357 energy

def build_unstake_transaction(params):
    """
    Build an UnfreezeBalanceV2 transaction
    
    Args:
        params: {
            'amount': float - TRX amount to unstake
            'from_address': str - Sender address
            'resource': str - 'ENERGY' or 'BANDWIDTH' (default: ENERGY)
            'network': str - 'mainnet', 'nile', or 'shasta'
        }
    
    Returns:
        dict: Transaction object ready for signing
    """
    
    # Parse parameters
    try:
        amount = float(params.get('amount', 0))
        from_address = params.get('from_address', '')
        resource = params.get('resource', 'ENERGY').upper()
        network = params.get('network', 'nile').lower()
        
        if amount <= 0:
            raise ValueError("Unstake amount must be positive")
        
        if not from_address:
            raise ValueError("Sender address is required")
        
        if resource not in ['ENERGY', 'BANDWIDTH']:
            raise ValueError("Resource must be 'ENERGY' or 'BANDWIDTH'")
            
    except Exception as e:
        return {'error': f'Parameter validation failed: {str(e)}'}
    
    # Convert amount to SUN (1 TRX = 1,000,000 SUN)
    amount_sun = int(amount * 1_000_000)
    
    # Select network
    network_endpoints = {
        'mainnet': 'https://api.trongrid.io',
        'nile': 'https://nile.trongrid.io',
        'shasta': 'https://api.shasta.trongrid.io'
    }
    
    full_node = network_endpoints.get(network, network_endpoints['nile'])
    
    try:
        # Initialize Tron client
        print(f"[DEBUG] Connecting to {network} network: {full_node}")
        tron_client = Tron(network=full_node)
        
        # Build UnfreezeBalanceV2 transaction
        print(f"[DEBUG] Building unstake transaction for {amount} TRX ({amount_sun} SUN)")
        print(f"[DEBUG] Resource type: {resource}")
        
        txn = tron_client.trx.unfreeze_balance_v2(
            unfreeze_balance=amount_sun,
            resource=resource
        )
        
        print(f"[DEBUG] Unstake transaction built successfully")
        
        # Get complete transaction from node
        try:
            sign_weight = tron_client.get_sign_weight(txn)
            if 'transaction' in sign_weight and 'transaction' in sign_weight['transaction']:
                tx_json = sign_weight['transaction']['transaction']
                print(f"[DEBUG] Using node transaction with raw_data_hex")
            else:
                tx_json = txn.to_json()
                tx_json.pop('permission', None)
                tx_json.pop('signature', None)
                print(f"[DEBUG] Using original transaction")
        except Exception as e:
            print(f"[WARNING] Failed to fetch from node: {e}")
            tx_json = txn.to_json()
            tx_json.pop('permission', None)
            tx_json.pop('signature', None)
        
        # Calculate energy/bandwidth loss
        energy_lost = int(amount * ENERGY_PER_TRX) if resource == 'ENERGY' else 0
        bandwidth_lost = int(amount * 1000) if resource == 'BANDWIDTH' else 0
        
        result = {
            'transaction': tx_json,
            'metadata': {
                'type': 'UNFREEZE_BALANCE_V2',
                'resource': resource,
                'amount': amount,
                'amount_sun': amount_sun,
                'energy_lost': energy_lost,
                'bandwidth_lost': bandwidth_lost,
                'instructions': [
                    f'1. You are unstaking {amount} TRX',
                    f'2. You will lose approximately {energy_lost if resource == "ENERGY" else bandwidth_lost:,} {resource.lower()}',
                    f'3. Your {amount} TRX will be immediately available',
                    '4. Resource calculation updates after ~3 days (withdraw delay)',
                    '5. Sign the transaction in your wallet to confirm'
                ]
            }
        }
        
        print(f"[SUCCESS] Unstake transaction ready")
        print(f"  Amount: {amount} TRX")
        print(f"  Resource: {resource}")
        print(f"  {resource} lost: {energy_lost if resource == 'ENERGY' else bandwidth_lost:,}")
        
        return result
        
    except Exception as e:
        error_msg = f"Failed to build unstake transaction: {str(e)}"
        print(f"[ERROR] {error_msg}")
        return {'error': error_msg}


if __name__ == '__main__':
    # Read params from stdin
    params = json.loads(sys.stdin.read())
    result = build_unstake_transaction(params)
    print(json.dumps(result, indent=2))
