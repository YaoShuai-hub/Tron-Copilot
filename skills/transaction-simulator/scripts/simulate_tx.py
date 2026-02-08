"""
Simulate transactions before execution to preview outcomes and prevent failures.
"""
import httpx
from src.config import Config
from typing import Dict
from tronpy import Tron
from tronpy.providers import HTTPProvider

TRONGRID_BASE = Config.TRONGRID_BASE if hasattr(Config, 'TRONGRID_BASE') else "https://nile.trongrid.io"

async def simulate_transaction(tx_params: Dict) -> Dict:
    """
    Simulate a transaction without executing it.
    
    Args:
        tx_params: Transaction parameters
            - from: Sender address
            - to: Recipient/contract address
            - value: Amount (optional)
            - data: Contract call data (optional)
            - function: Function name (optional)
            - args: Function arguments (optional)
            
    Returns:
        Dict with simulation results
    """
    try:
        # Method 1: Try TronGrid's triggersmartcontract endpoint
        if tx_params.get('to') and _is_contract(tx_params['to']):
            result = await _simulate_contract_call(tx_params)
        else:
            # Simple transfer simulation
            result = await _simulate_transfer(tx_params)
        
        return result
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': 'Simulation failed - transaction may fail if executed'
        }

async def _simulate_contract_call(tx_params: Dict) -> Dict:
    """Simulate smart contract interaction."""
    try:
        headers = {}
        if Config.TRONGRID_API_KEY:
            headers['TRON-PRO-API-KEY'] = Config.TRONGRID_API_KEY
        
        # Use TronGrid's triggersmartcontract for simulation
        async with httpx.AsyncClient(timeout=30.0) as client:
            url = f"{TRONGRID_BASE}/wallet/triggersmartcontract"
            
            payload = {
                'owner_address': tx_params['from'],
                'contract_address': tx_params['to'],
                'function_selector': tx_params.get('function', ''),
                'parameter': tx_params.get('data', ''),
                'visible': True
            }
            
            if tx_params.get('value'):
                payload['call_value'] = int(tx_params['value'])
            
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if simulation succeeded
                if data.get('result', {}).get('result'):
                    return {
                        'success': True,
                        'gas_used': data.get('energy_used', 0),
                        'output': data.get('constant_result', []),
                        'message': '✅ Transaction will succeed',
                        'simulation_data': data
                    }
                else:
                    return {
                        'success': False,
                        'error': data.get('result', {}).get('message', 'Unknown error'),
                        'message': '❌ Transaction will fail',
                        'simulation_data': data
                    }
            else:
                return {
                    'success': False,
                    'error': f'API error: {response.status_code}',
                    'message': 'Could not simulate transaction'
                }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': 'Simulation error'
        }

async def _simulate_transfer(tx_params: Dict) -> Dict:
    """Simulate simple TRX transfer."""
    try:
        # For simple transfers, check balance
        from_addr = tx_params['from']
        amount = tx_params.get('value', 0)
        
        # Get sender balance (simplified)
        balance = await _get_balance(from_addr)
        
        if balance >= amount:
            return {
                'success': True,
                'gas_used': 0,  # TRX transfers don't use energy
                'bandwidth_used': 270,  # Approximate
                'message': '✅ Transfer will succeed',
                'warning': None
            }
        else:
            return {
                'success': False,
                'error': f'Insufficient balance: {balance} TRX < {amount} TRX',
                'message': '❌ Transfer will fail - insufficient balance'
            }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': 'Could not simulate transfer'
        }

async def _get_balance(address: str) -> float:
    """Get TRX balance (simplified)."""
    try:
        headers = {}
        if Config.TRONGRID_API_KEY:
            headers['TRON-PRO-API-KEY'] = Config.TRONGRID_API_KEY
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{TRONGRID_BASE}/wallet/getaccount"
            payload = {'address': address, 'visible': True}
            
            response = await client.post(url, json=payload, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                balance_sun = data.get('balance', 0)
                return balance_sun / 1_000_000
    except:
        pass
    
    return 0

def _is_contract(address: str) -> bool:
    """Check if address is a contract (simplified heuristic)."""
    # Simple check: contracts often start with 'T' and are 34 chars
    # Real implementation would query the blockchain
    return len(address) == 34 and address.startswith('T')

def format_simulation_result(result: Dict, operation_desc: str = "") -> str:
    """Format simulation result for user display."""
    output = f"""🎮 Transaction Simulation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Operation: {operation_desc}
"""
    
    if result['success']:
        output += f"Simulation: ✅ SUCCESS\n\n"
        output += f"Expected Results:\n"
        if result.get('output'):
            output += f"  • Output: {result['output']}\n"
        output += f"\nCosts:\n"
        if result.get('gas_used'):
            output += f"  • Gas Used: ~{result['gas_used']:,} Energy\n"
        if result.get('bandwidth_used'):
            output += f"  • Bandwidth: ~{result['bandwidth_used']} points\n"
        output += f"\n✅ Transaction will succeed\n💡 Proceed with confidence!"
    else:
        output += f"Simulation: ❌ FAILED\n\n"
        output += f"Error: {result.get('error', 'Unknown error')}\n\n"
        output += f"🚨 DO NOT EXECUTE THIS TRANSACTION!\n"
        output += f"💡 {result.get('message', 'Transaction would fail')}"
    
    return output
