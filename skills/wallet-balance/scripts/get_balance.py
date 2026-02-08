"""
Enhanced wallet balance fetching with portfolio analysis.
"""
import httpx
import asyncio
from typing import Dict, List
from src.config import Config

# Load the token-price skill dynamically
import importlib.util
from pathlib import Path

def _load_token_price_skill():
    """Dynamically load token-price skill to avoid import issues."""
    skill_path = Path(__file__).parent.parent.parent / "token-price/scripts/fetch_price.py"
    spec = importlib.util.spec_from_file_location("fetch_price", skill_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.get_token_price

get_token_price = _load_token_price_skill()

async def get_wallet_balance(address: str) -> Dict:
    """
    Get complete wallet portfolio with USD valuations.
    
    Args:
        address: TRON wallet address (starts with T)
        
    Returns:
        Dict with portfolio data
    """
    # Validate address
    if not _is_valid_tron_address(address):
        return {
            'error': 'Invalid TRON address',
            'address': address
        }
    
    # Fetch token data from TronScan
    tokens = await _fetch_account_tokens(address)
    
    if 'error' in tokens:
        return tokens
    
    # Fetch prices for all tokens in parallel
    token_list = tokens.get('data', [])
    price_tasks = [
        get_token_price(token.get('tokenAbbr', 'UNKNOWN'))
        for token in token_list
    ]
    prices = await asyncio.gather(*price_tasks)
    
    # Calculate portfolio
    portfolio = []
    total_value = 0.0
    
    for i, token in enumerate(token_list):
        symbol = token.get('tokenAbbr', 'Unknown')
        decimals = int(token.get('tokenDecimal', 6))
        raw_balance = float(token.get('balance', 0))
        amount = raw_balance / (10 ** decimals)
        
        if amount <= 0:
            continue
            
        price_data = prices[i]
        usd_price = price_data.get('usd_price', 0.0)
        value = amount * usd_price
        total_value += value
        
        portfolio.append({
            'symbol': symbol,
            'name': token.get('tokenName', 'Unknown'),
            'amount': amount,
            'usd_price': usd_price,
            'value': value,
            'contract': token.get('tokenId', '')
        })
    
    # Sort by value
    portfolio.sort(key=lambda x: x['value'], reverse=True)
    
    # Calculate percentages
    for item in portfolio:
        item['percentage'] = (item['value'] / total_value * 100) if total_value > 0 else 0
    
    return {
        'address': address,
        'total_value_usd': total_value,
        'token_count': len(portfolio),
        'portfolio': portfolio
    }

async def _fetch_account_tokens(address: str) -> Dict:
    """Fetch token balances from TronScan API."""
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(
                f"{Config.TRONSCAN_URL}/account/tokens",
                params={
                    'address': address,
                    'start': 0,
                    'limit': 50,
                    'hidden': 0,
                    'show': 0,
                    'sortType': 0
                }
            )
            
            if resp.status_code == 200:
                return resp.json()
            else:
                return {'error': f'TronScan API error: {resp.status_code}'}
    except Exception as e:
        return {'error': str(e)}

def _is_valid_tron_address(address: str) -> bool:
    """Validate TRON address format."""
    if not address:
        return False
    if not address.startswith('T'):
        return False
    if len(address) != 34:
        return False
    # Basic Base58 character check
    valid_chars = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz'
    return all(c in valid_chars for c in address)
