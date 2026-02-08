"""
Address security checker using TronScan Security API.
Detects blacklisted addresses, fraud history, and malicious actors.
"""
import httpx
from src.config import Config
from typing import Dict
import asyncio

# TronScan Security API
TRONSCAN_BASE = Config.TRONSCAN_BASE if hasattr(Config, 'TRONSCAN_BASE') else "https://nileapi.tronscan.org/api"

async def check_address_security(address: str) -> Dict:
    """
    Check if a TRON address is safe to interact with.
    
    Args:
        address: TRON address to check (TBase58 format)
        
    Returns:
        Dict with security analysis:
        {
            'address': str,
            'is_safe': bool,
            'risk_level': 'SAFE'|'LOW'|'MEDIUM'|'HIGH'|'CRITICAL',
            'blacklisted': bool,
            'fraud_transactions': bool,
            'labels': list,
            'warnings': list,
            'recommendation': str
        }
    """
    try:
        # Validate address format
        if not _is_valid_address(address):
            return {
                'error': 'Invalid address format',
                'address': address,
                'is_safe': False,
                'risk_level': 'UNKNOWN'
            }
        
        # Call TronScan Security API
        url = f"{TRONSCAN_BASE}/account/security"
        params = {'address': address}
        
        headers = {}
        if Config.TRONSCAN_API_KEY:
            headers['TRON-PRO-API-KEY'] = Config.TRONSCAN_API_KEY
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return _analyze_security_data(address, data)
            elif response.status_code == 404:
                # Address not found in database - likely new/safe
                return {
                    'address': address,
                    'is_safe': True,
                    'risk_level': 'LOW',
                    'blacklisted': False,
                    'fraud_transactions': False,
                    'labels': [],
                    'warnings': ['Address not found in TronScan database (new address)'],
                    'recommendation': 'Low risk - address has no history'
                }
            else:
                # API error - fall back to basic checks
                return _fallback_check(address)
    
    except asyncio.TimeoutError:
        return _fallback_check(address, error="API timeout")
    except Exception as e:
        return _fallback_check(address, error=str(e))

def _analyze_security_data(address: str, data: Dict) -> Dict:
    """Analyze TronScan security response."""
    warnings = []
    is_safe = True
    risk_level = 'SAFE'
    
    # Check blacklist status
    is_blacklisted = data.get('is_black_list', False) or data.get('blacklisted', False)
    
    # Check fraud transactions
    has_fraud = data.get('has_fraud_transaction', False) or data.get('fraud_detected', False)
    
    # Check labels/tags
    labels = data.get('labels', []) or data.get('tags', [])
    
    # Analyze risks
    if is_blacklisted:
        warnings.append('🚨 Address is on stablecoin blacklist')
        is_safe = False
        risk_level = 'CRITICAL'
    
    if has_fraud:
        warnings.append('⚠️ Fraud transactions detected in history')
        is_safe = False
        if risk_level != 'CRITICAL':
            risk_level = 'HIGH'
    
    # Check for scam/phishing labels
    dangerous_labels = ['scam', 'phishing', 'fraud', 'malicious', 'hack', 'rugpull']
    for label in labels:
        label_lower = str(label).lower()
        if any(danger in label_lower for danger in dangerous_labels):
            warnings.append(f'🚨 Reported as: {label}')
            is_safe = False
            risk_level = 'CRITICAL'
    
    # Additional risk indicators
    if data.get('suspicious_activity'):
        warnings.append('⚠️ Suspicious activity pattern detected')
        if risk_level == 'SAFE':
            risk_level = 'MEDIUM'
    
    # Generate recommendation
    if risk_level == 'CRITICAL':
        recommendation = '🛑 STRONGLY RECOMMEND: DO NOT INTERACT - Confirmed malicious address'
    elif risk_level == 'HIGH':
        recommendation = '🛑 NOT RECOMMENDED: High fraud risk detected'
    elif risk_level == 'MEDIUM':
        recommendation = '⚠️ CAUTION ADVISED: Multiple warning signs present'
    elif risk_level == 'LOW':
        recommendation = '⚠️ Low risk - minor warnings present, proceed with care'
    else:
        recommendation = '✅ Safe to interact - no risks detected'
    
    return {
        'address': address,
        'is_safe': is_safe,
        'risk_level': risk_level,
        'blacklisted': is_blacklisted,
        'fraud_transactions': has_fraud,
        'labels': labels,
        'warnings': warnings,
        'recommendation': recommendation
    }

def _fallback_check(address: str, error: str = None) -> Dict:
    """Basic fallback check when API unavailable."""
    # Known safe addresses (official contracts)
    SAFE_ADDRESSES = {
        'TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t': 'USDT Token Contract',
        'TPYmHEhy5n8TCEfYGqW2rPxsghSfzghPDn': 'USDD Stablecoin',
        'TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax': 'SunSwap V2 Router'
    }
    
    if address in SAFE_ADDRESSES:
        return {
            'address': address,
            'is_safe': True,
            'risk_level': 'SAFE',
            'blacklisted': False,
            'fraud_transactions': False,
            'labels': [SAFE_ADDRESSES[address]],
            'warnings': [f'API unavailable ({error})' if error else 'Using fallback check'],
            'recommendation': '✅ Verified official contract'
        }
    
    return {
        'address': address,
        'is_safe': None,  # Unknown
        'risk_level': 'UNKNOWN',
        'blacklisted': False,
        'fraud_transactions': False,
        'labels': [],
        'warnings': [f'Security API unavailable ({error})' if error else 'API check failed'],
        'recommendation': '⚠️ Unable to verify - proceed with extreme caution or try again'
    }

def _is_valid_address(address: str) -> bool:
    """Validate TRON address format."""
    # Basic Base58 check (TRON uses standard Base58 check)
    # 123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz
    valid_chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    for c in address:
        if c not in valid_chars:
            return False
            
    return True
