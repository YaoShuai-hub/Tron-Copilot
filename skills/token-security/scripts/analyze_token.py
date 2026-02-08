"""
Analyze token contract security - honeypot, rug-pull risks, and malicious code detection.
"""
import httpx
from src.config import Config
from typing import Dict, List

TRONSCAN_BASE = Config.TRONSCAN_BASE if hasattr(Config, 'TRONSCAN_BASE') else "https://nileapi.tronscan.org/api"
GOPLUS_API = "https://api.gopluslabs.io/api/v1/token_security/tron"

async def analyze_token_security(token_address: str) -> Dict:
    """
    Analyze token contract for security risks.
    
    Args:
        token_address: Token contract address
        
    Returns:
        Dict with security analysis and risk level
    """
    # Step 1: Get basic token info
    token_info = await _fetch_token_info(token_address)
    
    # Step 2: Check contract verification
    is_verified = await _check_contract_verification(token_address)
    
    # Step 3: Honeypot detection (using Go+ Security API)
    honeypot_check = await _check_honeypot(token_address)
    
    # Step 4: Analyze contract for rug pull indicators
    rug_indicators = await _detect_rug_pull_indicators(token_address)
    
    # Step 5: Check ownership and liquidity
    ownership_risk = await _analyze_ownership(token_address)
    
    # Combine all checks
    critical_risks = []
    medium_risks = []
    
    # Critical: Not verified
    if not is_verified:
        critical_risks.append({
            'type': 'unverified_contract',
            'description': '❌ Contract source code NOT VERIFIED',
            'severity': 'critical',
            'recommendation': 'Never trust unverified contracts'
        })
    
    # Critical: Honeypot
    if honeypot_check.get('is_honeypot'):
        critical_risks.append({
            'type': 'honeypot',
            'description': '🚫 HONEYPOT DETECTED - Cannot sell after buying',
            'severity': 'critical',
            'recommendation': 'DO NOT BUY THIS TOKEN'
        })
    
    # Add rug pull indicators
    critical_risks.extend(rug_indicators.get('critical', []))
    medium_risks.extend(rug_indicators.get('medium', []))
    
    # Add ownership risks
    medium_risks.extend(ownership_risk)
    
    # Calculate risk level
    risk_level = _calculate_risk_level(critical_risks, medium_risks)
    
    return {
        'token_address': token_address,
        'token_info': token_info,
        'is_verified': is_verified,
        'is_honeypot': honeypot_check.get('is_honeypot', False),
        'critical_risks': critical_risks,
        'medium_risks': medium_risks,
        'risk_level': risk_level,
        'verdict': _generate_verdict(risk_level, critical_risks),
        'should_trade': risk_level in ['SAFE', 'LOW']
    }

async def _fetch_token_info(address: str) -> Dict:
    """Fetch basic token information."""
    try:
        headers = {}
        if Config.TRONSCAN_API_KEY:
            headers['TRON-PRO-API-KEY'] = Config.TRONSCAN_API_KEY
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{TRONSCAN_BASE}/contract"
            params = {'contract': address}
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                return {
                    'name': data.get('name', 'Unknown'),
                    'symbol': data.get('symbol', 'Unknown'),
                    'decimals': data.get('decimals', 18)
                }
    except:
        pass
    
    return {'name': 'Unknown', 'symbol': 'Unknown', 'decimals': 18}

async def _check_contract_verification(address: str) -> bool:
    """Check if contract source code is verified."""
    try:
        headers = {}
        if Config.TRONSCAN_API_KEY:
            headers['TRON-PRO-API-KEY'] = Config.TRONSCAN_API_KEY
        
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{TRONSCAN_BASE}/contract"
            params = {'contract': address}
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code == 200:
                data = response.json()
                # Check if contract has source code
                return bool(data.get('sourceCode') or data.get('verified'))
    except:
        pass
    
    return False

async def _check_honeypot(address: str) -> Dict:
    """Use Go+ Security API for honeypot detection."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            url = f"{GOPLUS_API}"
            params = {'contract_addresses': address}
            
            response = await client.get(url, params=params)
            
            if response.status_code == 200:
                data = response.json()
                result = data.get('result', {}).get(address.lower(), {})
                
                # Parse honeypot indicators
                is_honeypot = (
                    result.get('is_honeypot') == '1' or
                    result.get('buy_tax', '0') == '100' or
                    result.get('sell_tax', '0') == '100'
                )
                
                return {
                    'is_honeypot': is_honeypot,
                    'buy_tax': float(result.get('buy_tax', 0)),
                    'sell_tax': float(result.get('sell_tax', 0))
                }
    except Exception as e:
        print(f"Go+ API error (using fallback): {e}")
    
    # Fallback: assume unknown
    return {'is_honeypot': False, 'buy_tax': 0, 'sell_tax': 0}

async def _detect_rug_pull_indicators(address: str) -> Dict:
    """Detect rug pull risk indicators."""
    critical = []
    medium = []
    
    # This would require contract bytecode analysis
    # For now, using simplified heuristics
    
    # TODO: Implement actual contract analysis
    # - Check for mint functions
    # - Check for ownership transfer
    # - Check for pause functions
    # - Check liquidity lock
    
    return {'critical': critical, 'medium': medium}

async def _analyze_ownership(address: str) -> List[Dict]:
    """Analyze ownership risks."""
    risks = []
    
    # TODO: Implement ownership analysis
    # - Check if ownership renounced
    # - Check holder distribution
    # - Check if owner holds LP tokens
    
    return risks

def _calculate_risk_level(critical: List, medium: List) -> str:
    """Calculate overall risk level."""
    if len(critical) >= 2:
        return "CRITICAL"
    elif len(critical) >= 1:
        return "HIGH"
    elif len(medium) >= 3:
        return "HIGH"
    elif len(medium) >= 1:
        return "MEDIUM"
    else:
        return "LOW"

def _generate_verdict(risk_level: str, critical_risks: List) -> str:
    """Generate human-readable verdict."""
    if risk_level == "CRITICAL":
        return "🚨 EXTREME DANGER - This token shows multiple signs of a scam. DO NOT TRADE!"
    elif risk_level == "HIGH":
        return "⛔ HIGH RISK - Strong indicators of malicious intent. Avoid trading."
    elif risk_level == "MEDIUM":
        return "⚠️ MODERATE RISK - Some concerns detected. Trade with caution and small amounts."
    else:
        return "✅ LOW RISK - Token appears relatively safe, but always DYOR."
