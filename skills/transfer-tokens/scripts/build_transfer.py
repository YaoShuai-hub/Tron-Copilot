"""
Build unsigned transfer transactions for TRX and TRC20 tokens.

This skill orchestrates multiple sub-skills:
1. address-book: Lookup recipient alias
2. malicious-address-detector: Check TronScan blacklist
3. address-risk-checker: Security risk assessment
4. energy-rental: Calculate energy requirements (for TRC20)
5. Build and return unsigned transaction
"""
from tronpy import Tron
from tronpy.providers import HTTPProvider
from tronpy.keys import to_base58check_address
from src.config import Config
import json
import time
import sys
from pathlib import Path
from typing import Dict, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import sub-skills with correct paths
try:
    sys.path.insert(0, str(PROJECT_ROOT / "skills" / "address-book" / "scripts"))
    from manage_contacts import get_contact_alias, save_contact
except (ImportError, Exception) as e:
    print(f"[WARN] Failed to import address-book: {e}")
    get_contact_alias = None
    save_contact = None

try:
    sys.path.insert(0, str(PROJECT_ROOT / "skills" / "malicious-address-detector" / "scripts"))
    from check_malicious import check_malicious_address
except (ImportError, Exception) as e:
    print(f"[WARN] Failed to import malicious-address-detector: {e}")
    check_malicious_address = None

try:
    sys.path.insert(0, str(PROJECT_ROOT / "skills" / "address-risk-checker" / "scripts"))
    from check_address import check_address_security as _check_security
except (ImportError, Exception) as e:
    print(f"[WARN] Failed to import address-risk-checker: {e}")
    _check_security = None

try:
    sys.path.insert(0, str(PROJECT_ROOT / "skills" / "energy-rental" / "scripts"))
    from calculate_rental import get_rental_proposal
except (ImportError, Exception) as e:
    print(f"[WARN] Failed to import energy-rental: {e}")
    get_rental_proposal = None

# Network-specific token addresses
TOKEN_ADDRESSES = {
    'mainnet': {
        'USDT': 'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t',
        'USDD': 'TPYmHEhy5n8TCEfYGqW2rPxsghSfzghPDn',
        'BTT': 'TAFjULxiVgT4qWk6UZwjqwZXTSaGaqnVp4',
        'JST': 'TCFLL5dx5ZJdKnWuesXxi1VPwjLVmWZZy9',
        'SUN': 'TSSMHYeV2uE9qYH95DqyoCuNCzEL1NvU3S'
    },
    'nile': {
        'USDT': 'TXYZopYRdj2D9XRtbG411XZZ3kM5VkAeBf',  # Nile testnet USDT
        # Add more Nile testnet tokens as needed
    },
    'shasta': {
        # Add Shasta testnet tokens as needed
    }
}

def _get_tron_client(network: str = "nile"):
    """Get Tron client configured for specific network."""
    # tronpy's Tron(network=) accepts 'mainnet', 'nile', 'shasta' strings
    # Map our network param (which already uses these names) directly
    if network in ['mainnet', 'nile', 'shasta']:
        tronpy_network = network
    elif network == 'unknown':
        tronpy_network = 'nile'  # Default fallback
    else:
        tronpy_network = 'nile'  # Safe fallback
    
    # Initialize Tron client with network name
    client = Tron(network=tronpy_network)
    
    # Set API key if available
    if Config.TRONGRID_API_KEY:
        client.provider.api_key = Config.TRONGRID_API_KEY
    
    return client

async def build_transfer_transaction(
    from_address: str,
    to_address: str,
    token: str,
    amount: float,
    memo: str = "",
    network: str = "nile"
) -> Dict:
    """
    Build an unsigned transfer transaction for TRX or TRC20 tokens.
    
    This function orchestrates multiple security and optimization skills.
    
    Args:
        from_address: Sender wallet address
        to_address: Recipient wallet address  
        token: "TRX" or TRC20 contract address
        amount: Amount to transfer
        memo: Optional memo (only for TRX transfers)
        network: Network to use (mainnet, nile, shasta)
        
    Returns:
        Dict with unsigned transaction and metadata
    """
    try:
        print(f"\n🔧 [SKILL ORCHESTRATION] transfer-tokens")
        print(f"   From: {from_address[:6]}...{from_address[-6:]}")
        print(f"   To: {to_address[:6]}...{to_address[-6:]}")
        print(f"   Amount: {amount} {token}")
        print(f"   Network: {network}")
        
        # Initialize Tron client with correct network
        tron_client = _get_tron_client(network)
        
        # Validate addresses
        if not _is_valid_address(from_address):
            return {'error': f'Invalid sender address: {from_address}'}
        if not _is_valid_address(to_address):
            return {'error': f'Invalid recipient address: {to_address}'}
        
        # Validate amount
        if amount <= 0:
            return {'error': 'Amount must be greater than 0'}
        
        # === SKILL 1: Address Book - Record Transfer ===
        print("\n📇 [SKILL] address-book: Recording transfer...")
        if get_contact_alias and save_contact:
            try:
                # Get existing alias (synchronous)
                alias = get_contact_alias(to_address)
                
                # Record this transfer (increment count)
                contact_info = save_contact(to_address, alias=alias, increment_count=True)
                transfer_count = contact_info.get('transfer_count', 1)
                
                if alias:
                    print(f"   ✅ Sending to saved contact: '{alias}' (Transfer #{transfer_count})")
                else:
                    print(f"   ℹ️ New recipient recorded (Transfer #{transfer_count})")
                    print(f"   💡 Tip: Use /save-contact to add a name for this address")
            except Exception as e:
                print(f"   ⚠️ Address book recording failed: {e}")
        else:
            print("   ⚠️ Address book skill not available")
        
        # === SKILL 2: Malicious Address Detection ===
        print("\n🚨 [SKILL] malicious-address-detector: Checking TronScan blacklist...")
        if check_malicious_address:
            try:
                malicious_check = await check_malicious_address(to_address, network)
                if malicious_check['is_malicious']:
                    error_msg = f"🚨 DANGER: {malicious_check['warnings'][0]}"
                    print(f"   {error_msg}")
                    return {'error': error_msg}
                elif malicious_check['risk_level'] == 'WARNING':
                    print(f"   ⚠️ Warning: {malicious_check['warnings'][0]}")
                else:
                    print(f"   ✅ No malicious tags detected")
            except Exception as e:
                print(f"   ⚠️ Malicious check failed: {e}")
        else:
            print("   ⚠️ Malicious detector skill not available")
        
        # === SKILL 3: Security Risk Assessment ===
        print("\n🔒 [SKILL] address-risk-checker: Running security assessment...")
        if _check_security:
            try:
                security_check = await _check_security(to_address)
                risk = security_check.get('risk_level', 'UNKNOWN')
                if risk in ['CRITICAL', 'HIGH']:
                    print(f"   ⚠️ {risk} RISK: {security_check.get('summary', 'Unknown risk')}")
                elif risk == 'MEDIUM':
                    print(f"   ⚠️ Medium risk detected")
                else:
                    print(f"   ✅ Security check passed ({risk})")
            except Exception as e:
                print(f"   ⚠️ Security check failed: {e}")
        else:
            print("   ⚠️ Security checker skill not available")
        
        # === SKILL 4: Energy Rental Calculation (TRC20 only) ===
        is_trx = (token.upper() == 'TRX')
        if not is_trx:
            print("\n⚡ [SKILL] energy-rental: Calculating energy requirements...")
            if get_rental_proposal:
                try:
                    # TRC20 transfers typically need ~28,000 energy
                    energy_needed = 28000
                    rental_info = await get_rental_proposal(energy_needed, 1, network)
                    if rental_info and 'recommendation' in rental_info:
                        action = rental_info['recommendation'].get('action', 'unknown')
                        print(f"   💡 Recommendation: {action.upper()}")
                        if action == 'rent':
                            cost = rental_info['rental_options'][0]['cost_trx'] if rental_info.get('rental_options') else 0
                            print(f"   💰 Estimated rental cost: {cost:.2f} TRX")
                except Exception as e:
                    print(f"   ⚠️ Energy calculation failed: {e}")
            else:
                print("   ⚠️ Energy rental skill not available")
        
        print("\n🔨 [SKILL] Building transaction...")
        import asyncio
        
        # Determine transfer type
        is_trx = (token.upper() == 'TRX')
        
        if is_trx:
            # TRX transfer
            amount_sun = int(amount * 1_000_000)  # Convert to SUN
            
            # Helper for blocking build
            def _build_trx_blocking():
                return (
                    tron_client.trx.transfer(from_address, to_address, amount_sun)
                    .memo(memo) if memo else
                    tron_client.trx.transfer(from_address, to_address, amount_sun)
                ).build()

            # Run in thread
            try:
                txn = await asyncio.to_thread(_build_trx_blocking)
            except Exception as e:
                return {'error': f"Failed to build TRX transaction: {e}"}
            
            print(f"[DEBUG] TRX transaction built successfully")
            
            # Get the complete transaction from node (blocking)
            try:
                def _get_sign_weight_blocking():
                    return tron_client.get_sign_weight(txn)
                    
                sign_weight = await asyncio.to_thread(_get_sign_weight_blocking)
                
                if 'transaction' in sign_weight and 'transaction' in sign_weight['transaction']:
                    # Use the transaction object returned by the node (hex addresses, no visible flag needed)
                    tx_json = sign_weight['transaction']['transaction']
                    print(f"[DEBUG] Using node transaction with raw_data_hex")
                else:
                    raise ValueError("Node response missing transaction data")
            except Exception as e:
                print(f"[WARNING] Failed to fetch from node: {e}")
                tx_json = txn.to_json()
                tx_json.pop('permission', None)
                tx_json.pop('signature', None)
            
            print(f"[DEBUG] Transaction JSON: {tx_json}")
            
            result = {
                'transaction': tx_json,
                'metadata': {
                    'type': 'TRX_TRANSFER',
                    'token': 'TRX',
                    'amount': amount,
                    'recipient': to_address,
                    'memo': memo,
                    'estimated_energy': 0,
                    'estimated_bandwidth': 270,
                    'estimated_cost_trx': 0,
                    'instructions': [
                        '1. Review the recipient address carefully',
                        '2. Verify the amount',
                        '3. Ensure you have ~270 bandwidth (free if available)',
                        '4. Sign in your wallet and broadcast'
                    ]
                }
            }
            return result
            
        else:
            # TRC20 transfer
            token_address = _resolve_token_address(token, network)
            print(f"[DEBUG] Resolved token address: {token_address} for network {network}")
            
            # Get token contract (blocking)
            try:
                print(f"[DEBUG] Fetching contract for {token_address} on network {network}...")
                contract = await asyncio.to_thread(tron_client.get_contract, token_address)
                print(f"[DEBUG] Contract fetched successfully")
            except Exception as contract_error:
                print(f"[DEBUG] Failed to get contract: {str(contract_error)}")
                raise
            
            # Get token decimals (assume 6 for USDT/USDD, but should query)
            decimals = 6
            amount_int = int(amount * (10 ** decimals))
            print(f"[DEBUG] Amount in smallest unit: {amount_int}")
            
            # Build TRC20 transfer (blocking)
            print(f"[DEBUG] Building transfer transaction...")
            
            def _build_trc20_blocking():
                return (
                    contract.functions.transfer(to_address, amount_int)
                    .with_owner(from_address)
                    .fee_limit(100_000_000)
                    .build()
                )
                
            try:
                txn = await asyncio.to_thread(_build_trc20_blocking)
            except Exception as e:
                return {'error': f"Failed to build TRC20 transaction: {e}"}

            print(f"[DEBUG] Transaction built successfully")
            
            # Get the complete transaction from node (blocking)
            try:
                def _get_sign_weight_blocking():
                    return tron_client.get_sign_weight(txn)

                sign_weight = await asyncio.to_thread(_get_sign_weight_blocking)
                
                if 'transaction' in sign_weight and 'transaction' in sign_weight['transaction']:
                    tx_json = sign_weight['transaction']['transaction']
                    print(f"[DEBUG] Using node transaction with raw_data_hex")
                else:
                    raise ValueError("Node response missing transaction data")
            except Exception as e:
                print(f"[WARNING] Failed to fetch from node: {e}")
                tx_json = txn.to_json()
                tx_json.pop('permission', None)
                tx_json.pop('signature', None)
            
            result = {
                'transaction': tx_json,
                'metadata': {
                    'type': 'TRC20_TRANSFER',
                    'token': token_address,
                    'token_symbol': token.upper() if token.upper() in TOKEN_ADDRESSES else 'TRC20',
                    'amount': amount,
                    'recipient': to_address,
                    'estimated_energy': 28000,  # Typical for USDT
                    'estimated_bandwidth': 350,
                    'estimated_cost_trx': 1.2,  # If burning energy
                    'instructions': [
                        '1. Review the recipient address carefully',
                        '2. Verify the amount and token contract',
                        f'3. You need ~28,000 Energy (~1.2 TRX if burning)',
                        '4. Consider renting energy to save 70% on fees!',
                        '5. Sign in your wallet and broadcast'
                    ]
                }
            }
            return result
        
    except Exception as e:
        error_msg = str(e)
        
        # Check for common errors
        if '401' in error_msg or '429' in error_msg:
            return {
                'error': 'API error',
                'message': 'Add TRONGRID_API_KEY to config.toml for real transactions',
                'fallback': 'unsigned_tx'
            }
        
        if 'balance is not sufficient' in error_msg.lower():
            return {
                'error': 'Insufficient balance',
                'message': f'The sender does not have enough {token} to complete this transfer'
            }
        
        return {'error': f'Transaction build failed: {error_msg}'}

def _convert_addresses_to_base58(tx_json: dict) -> dict:
    """
    Convert all hex addresses in transaction JSON to base58 format.
    TronLink requires base58 addresses for signature verification.
    """
    if not isinstance(tx_json, dict):
        return tx_json
    
    result = {}
    for key, value in tx_json.items():
        if isinstance(value, str) and (key.endswith('_address') or key == 'address'):
            # This is an address field - convert if it's hex format
            if value.startswith('41') and len(value) == 42:
                try:
                    result[key] = to_base58check_address(value)
                    print(f"[DEBUG] Converted address {key}: {value} -> {result[key]}")
                except Exception as e:
                    print(f"[WARNING] Failed to convert address {value}: {e}")
                    result[key] = value
            else:
                result[key] = value
        elif isinstance(value, dict):
            result[key] = _convert_addresses_to_base58(value)
        elif isinstance(value, list):
            result[key] = [_convert_addresses_to_base58(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    
    return result
 
def _resolve_token_address(token: str, network: str = "nile") -> str:
    """Resolve token symbol to address for specific network."""
    token_upper = token.upper()
    
    # Check if it's a known token symbol
    if network in TOKEN_ADDRESSES and token_upper in TOKEN_ADDRESSES[network]:
        return TOKEN_ADDRESSES[network][token_upper]
    
    # Fallback to mainnet if network not found but token exists in mainnet
    if token_upper in TOKEN_ADDRESSES.get('mainnet', {}):
        print(f"[WARNING] Token {token_upper} not found for {network}, using mainnet address")
        return TOKEN_ADDRESSES['mainnet'][token_upper]
    
    # Assume it's already a contract address
    if token.startswith('T') and len(token) == 34:
        return token
    
    return token

def _is_valid_address(address: str) -> bool:
    """Validate TRON address format."""
    # Basic Base58 check
    # 123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz
    valid_chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    for c in address:
        if c not in valid_chars:
            return False
            
    return True
