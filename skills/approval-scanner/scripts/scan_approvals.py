"""
Scan wallet for token approvals and detect risky unlimited allowances.
"""
import httpx
from src.config import Config
from typing import Dict, List
from datetime import datetime

TRONSCAN_BASE = Config.TRONSCAN_BASE if hasattr(Config, 'TRONSCAN_BASE') else "https://nileapi.tronscan.org/api"
MAX_UINT256 = 2**256 - 1  # Unlimited approval indicator

async def scan_approvals(wallet_address: str) -> Dict:
    """
    Scan wallet for all token approvals.
    
    Args:
        wallet_address: TRON wallet address to scan
        
    Returns:
        Dict with approval analysis and risks
    """
    # Fetch approval events
    approvals = await _fetch_approval_events(wallet_address)
    
    if not approvals:
        return {
            'address': wallet_address,
            'total_approvals': 0,
            'risky_approvals': [],
            'medium_risk': [],
            'safe_approvals': [],
            'message': 'No token approvals found'
        }
    
    # Analyze each approval
    critical_risks = []
    medium_risks = []
    safe_approvals = []
    
    for approval in approvals:
        risk_level = _assess_approval_risk(approval)
        
        if risk_level == 'critical':
            critical_risks.append(approval)
        elif risk_level == 'medium':
            medium_risks.append(approval)
        else:
            safe_approvals.append(approval)
    
    return {
        'address': wallet_address,
        'total_approvals': len(approvals),
        'risky_approvals': critical_risks,
        'medium_risk': medium_risks,
        'safe_approvals': safe_approvals,
        'recommendations': _generate_recommendations(critical_risks, medium_risks)
    }

async def _fetch_approval_events(address: str) -> List[Dict]:
    """Fetch approval events from TronScan API."""
    try:
        headers = {}
        if Config.TRONSCAN_API_KEY:
            headers['TRON-PRO-API-KEY'] = Config.TRONSCAN_API_KEY
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Fetch TRC20 token transfers with 'approve' type
            url = f"{TRONSCAN_BASE}/contract/events"
            params = {
                'address': address,
                'event_name': 'Approval',
                'limit': 100
            }
            
            response = await client.get(url, params=params, headers=headers)
            
            if response.status_code != 200:
                # Fallback: try to get from account info
                return []
            
            data = response.json()
            events = data.get('data', [])
            
            # Parse approval events
            approvals = []
            for event in events:
                approval_data = _parse_approval_event(event)
                if approval_data:
                    approvals.append(approval_data)
            
            return approvals
    
    except Exception as e:
        print(f"Error fetching approvals: {e}")
        return []

def _parse_approval_event(event: Dict) -> Dict:
    """Parse approval event into structured format."""
    try:
        # Extract approval details
        result = event.get('result', {})
        
        return {
            'token': event.get('tokenAddress', 'Unknown'),
            'token_name': event.get('tokenName', 'Unknown'),
            'spender': result.get('spender', 'Unknown'),
            'amount': int(result.get('value', 0)),
            'timestamp': event.get('timestamp', 0),
            'tx_hash': event.get('transactionHash', ''),
            'is_unlimited': int(result.get('value', 0)) >= MAX_UINT256 * 0.9  # Close to max
        }
    except Exception as e:
        return None

def _assess_approval_risk(approval: Dict) -> str:
    """Assess risk level of an approval."""
    # Critical: Unlimited approval
    if approval.get('is_unlimited'):
        return 'critical'
    
    # Check amount
    amount = approval.get('amount', 0)
    
    # Critical: Very high allowance to unknown contract
    if amount > 1_000_000_000_000:  # > 1M tokens (in base units)
        # Check if contract is known/verified (simplified)
        spender = approval.get('spender', '')
        
        # Known safe contracts (SunSwap, JustSwap, etc.)
        known_safe = [
            'TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax',  # SunSwap V2 Router
            # Add more known contracts
        ]
        
        if spender not in known_safe:
            return 'critical'
        else:
            return 'medium'
    
    # Medium: High allowance
    if amount > 100_000_000_000:  # > 100K tokens
        return 'medium'
    
    # Safe: Limited allowance
    return 'safe'

def _generate_recommendations(critical: List[Dict], medium: List[Dict]) -> List[str]:
    """Generate security recommendations."""
    recommendations = []
    
    if critical:
        recommendations.append(
            f"🚨 URGENT: Revoke {len(critical)} critical approval(s) immediately to prevent potential token theft"
        )
    
    if medium:
        recommendations.append(
            f"⚠️ Review {len(medium)} medium-risk approval(s) and consider reducing allowances"
        )
    
    if not critical and not medium:
        recommendations.append("✅ All approvals appear safe. Continue monitoring monthly.")
    
    recommendations.append(
        "💡 Best practice: Use limited approvals instead of unlimited whenever possible"
    )
    
    return recommendations
