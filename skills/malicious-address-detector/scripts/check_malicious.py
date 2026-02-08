"""
Malicious Address Detector for TRON Blockchain

Checks TronScan's official tag/label database to detect:
- Scam addresses
- Phishing addresses  
- Fake/impersonation addresses
- Other malicious actors

Returns risk level and warnings for safe transaction decisions.
"""

import httpx
import asyncio
from typing import Dict, List, Optional
from datetime import datetime, timedelta

# Simple in-memory cache
_cache: Dict[str, tuple[Dict, datetime]] = {}
CACHE_DURATION = timedelta(minutes=5)

# Malicious tag patterns
DANGER_TAGS = {'scam', 'phishing', 'fake', 'fraud', 'malicious', 'hack', 'exploit'}
WARNING_TAGS = {'mixer', 'gambling', 'laundering', 'suspicious'}


def _is_cache_valid(address: str) -> bool:
    """Check if cached result is still valid."""
    if address not in _cache:
        return False
    _, cached_time = _cache[address]
    return datetime.now() - cached_time < CACHE_DURATION


def _get_cached(address: str) -> Optional[Dict]:
    """Get cached result if valid."""
    if _is_cache_valid(address):
        result, _ = _cache[address]
        return result
    return None


def _set_cache(address: str, result: Dict):
    """Cache result with timestamp."""
    _cache[address] = (result, datetime.now())


def _analyze_tags(tags: List[str]) -> tuple[str, List[str]]:
    """
    Analyze tags to determine risk level.
    
    Args:
        tags: List of string tags from TronScan
        
    Returns:
        (risk_level, warnings) tuple
    """
    if not tags:
        return "SAFE", []
    
    # Normalize tags
    tags_lower = {tag.lower() for tag in tags}
    
    # Check for danger tags
    danger_found = tags_lower & DANGER_TAGS
    if danger_found:
        warnings = [f"⚠️ Address tagged as {', '.join(danger_found)} on TronScan"]
        return "DANGER", warnings
    
    # Check for warning tags
    warning_found = tags_lower & WARNING_TAGS
    if warning_found:
        warnings = [f"⚠️ Address associated with {', '.join(warning_found)}"]
        return "WARNING", warnings
    
    return "SAFE", []


async def check_malicious_address(address: str, network: str = "mainnet") -> Dict:
    """
    Check if address is flagged as malicious on TronScan.
    
    Args:
        address: TRON address to check
        network: Network to check (mainnet by default, testnet not supported)
        
    Returns:
        {
            "is_malicious": bool,
            "risk_level": "SAFE|WARNING|DANGER",
            "tags": List[str],
            "warnings": List[str],
            "source": "tronscan",
            "address": str
        }
    """
    # Check cache first
    cached = _get_cached(address)
    if cached:
        return cached
    
    # Testnet doesn't have TronScan tag database
    if network in ['nile', 'shasta']:
        result = {
            "is_malicious": False,
            "risk_level": "SAFE",
            "tags": [],
            "warnings": [],
            "source": "tronscan_testnet_unavailable",
            "address": address
        }
        _set_cache(address, result)
        return result
    
    try:
        # Call TronScan API
        url = f"https://apilist.tronscanapi.com/api/account/tokens"
        params = {"address": address, "start": 0, "limit": 1}
        
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            
            data = response.json()
            
            # Extract tags from response
            tags = []
            if isinstance(data, dict):
                # Check various possible tag locations
                if 'tags' in data:
                    tags = data.get('tags', [])
                elif 'data' in data and isinstance(data['data'], list) and len(data['data']) > 0:
                    account_data = data['data'][0]
                    tags = account_data.get('tags', [])
            
            # Analyze tags
            risk_level, warnings = _analyze_tags(tags)
            
            result = {
                "is_malicious": risk_level == "DANGER",
                "risk_level": risk_level,
                "tags": tags,
                "warnings": warnings,
                "source": "tronscan",
                "address": address
            }
            
            # Cache result
            _set_cache(address, result)
            
            return result
                
    except asyncio.TimeoutError:
        print(f"[WARN] TronScan API timeout for {address}")
        return {
            "is_malicious": False,
            "risk_level": "UNKNOWN",
            "tags": [],
            "warnings": ["⚠️ Could not verify with TronScan (timeout)"],
            "source": "tronscan_timeout",
            "address": address
        }
    except Exception as e:
        print(f"[ERROR] Malicious address check failed: {e}")
        return {
            "is_malicious": False,
            "risk_level": "UNKNOWN",
            "tags": [],
            "warnings": [f"⚠️ Could not verify with TronScan ({str(e)[:50]})"],
            "source": "tronscan_error",
            "address": address
        }


# CLI interface for testing
if __name__ == '__main__':
    import sys
    import json
    
    async def main():
        if len(sys.argv) < 2:
            print(json.dumps({
                'error': 'Usage: python check_malicious.py <address> [network]'
            }, ensure_ascii=False, indent=2))
            sys.exit(1)
        
        address = sys.argv[1]
        network = sys.argv[2] if len(sys.argv) > 2 else "mainnet"
        
        result = await check_malicious_address(address, network)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    
    asyncio.run(main())
