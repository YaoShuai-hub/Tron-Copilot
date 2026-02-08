"""
Enhanced token price fetching with multiple data sources and caching.
"""
import httpx
import time
from typing import Dict, Optional
from src.config import Config

# Simple in-memory cache
_price_cache = {}
CACHE_TTL = 30  # seconds

async def get_token_price(symbol_or_address: str) -> Dict[str, any]:
    """
    Get token price from multiple sources with fallback.
    
    Args:
        symbol_or_address: Token symbol (e.g., 'TRX') or contract address
        
    Returns:
        Dict with price data: {symbol, usd_price, source, timestamp, change_24h}
    """
    # Check cache
    cache_key = symbol_or_address.upper()
    if cache_key in _price_cache:
        cached = _price_cache[cache_key]
        if time.time() - cached['timestamp'] < CACHE_TTL:
            return cached
    
    # Try multiple sources
    price_data = None
    
    # 1. Try Binance (most reliable for major tokens)
    price_data = await _fetch_from_binance(symbol_or_address)
    
    # 2. Fallback to CoinGecko
    if not price_data or price_data['usd_price'] == 0:
        price_data = await _fetch_from_coingecko(symbol_or_address)
    
    # 3. Fallback to on-chain (SunSwap)
    if not price_data or price_data['usd_price'] == 0:
        price_data = await _fetch_from_sunswap(symbol_or_address)
    
    # Cache result
    if price_data:
        _price_cache[cache_key] = price_data
        
    return price_data or {
        'symbol': symbol_or_address,
        'usd_price': 0.0,
        'source': 'none',
        'timestamp': time.time(),
        'change_24h': 0.0
    }

async def _fetch_from_binance(symbol: str) -> Optional[Dict]:
    """Fetch price from Binance API."""
    try:
        symbol_map = {
            'TRX': 'TRXUSDT',
            'BTC': 'BTCUSDT',
            'ETH': 'ETHUSDT',
            'USDT': 'USDT',
            'BTT': 'BTTUSDT'
        }
        
        if symbol.upper() == 'USDT':
            return {
                'symbol': 'USDT',
                'usd_price': 1.0,
                'source': 'stablecoin',
                'timestamp': time.time(),
                'change_24h': 0.0
            }
        
        ticker = symbol_map.get(symbol.upper())
        if not ticker:
            return None
            
        async with httpx.AsyncClient(timeout=10.0) as client:
            # Get 24h ticker data
            resp = await client.get(
                "https://api.binance.com/api/v3/ticker/24hr",
                params={'symbol': ticker}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                return {
                    'symbol': symbol.upper(),
                    'usd_price': float(data['lastPrice']),
                    'source': 'binance',
                    'timestamp': time.time(),
                    'change_24h': float(data['priceChangePercent'])
                }
    except Exception as e:
        print(f"Binance error: {e}")
        return None

async def _fetch_from_coingecko(symbol: str) -> Optional[Dict]:
    """Fetch price from CoinGecko API."""
    try:
        symbol_map = {
            'TRX': 'tron',
            'USDT': 'tether',
            'USDD': 'usdd',
            'BTT': 'bittorrent',
            'JST': 'just',
            'SUN': 'sun-token'
        }
        
        coin_id = symbol_map.get(symbol.upper())
        if not coin_id:
            return None
            
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={
                    'ids': coin_id,
                    'vs_currencies': 'usd',
                    'include_24hr_change': 'true'
                },
                headers={'User-Agent': 'BlockChain-Copilot/1.0'}
            )
            
            if resp.status_code == 200:
                data = resp.json()
                if coin_id in data:
                    return {
                        'symbol': symbol.upper(),
                        'usd_price': data[coin_id]['usd'],
                        'source': 'coingecko',
                        'timestamp': time.time(),
                        'change_24h': data[coin_id].get('usd_24h_change', 0.0)
                    }
    except Exception as e:
        print(f"CoinGecko error: {e}")
        return None

async def _fetch_from_sunswap(address: str) -> Optional[Dict]:
    """Fetch price from SunSwap DEX (for TRON-specific tokens)."""
    # TODO: Implement SunSwap price oracle query
    # This would query the SunSwap pair contract for token/USDT or token/TRX ratio
    return None
