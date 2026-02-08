"""
Energy rental cost calculator and platform comparator.
"""
from typing import Dict, List

# Energy rental platforms (rates in sun per energy per day)
RENTAL_PLATFORMS = [
    {
        'name': 'JustLend DAO',
        'rate_per_1k_per_day': 0.12,  # TRX
        'url': 'https://justlend.org/#/market',
        'safety': 'high',
        'min_rental': 10000
    },
    {
        'name': 'Justmoney Club',
        'rate_per_1k_per_day': 0.10,  # TRX
        'url': 'https://justmoney.club',
        'safety': 'high',
        'min_rental': 5000
    },
    {
        'name': 'Stake.Energy',
        'rate_per_1k_per_day': 0.15,  # TRX
        'url': 'https://stake.energy',
        'safety': 'medium',
        'min_rental': 32000
    }
]

# Current burn rate (approximate)
BURN_RATE_PER_ENERGY = 0.00042  # TRX per energy unit

async def get_rental_proposal(
    energy_needed: int,
    duration_days: int = 3,
    include_burn_comparison: bool = True
) -> Dict:
    """
    Generate energy rental proposal with cost comparison.
    
    Args:
        energy_needed: Amount of energy required
        duration_days: Rental duration in days
        include_burn_comparison: Whether to show burn cost comparison
        
    Returns:
        Dict with rental options and recommendations
    """
    if energy_needed <= 0:
        return {'error': 'Energy amount must be positive'}
    
    if duration_days < 1:
        return {'error': 'Duration must be at least 1 day'}
    
    # Calculate burn cost (if user has no energy)
    burn_cost_trx = energy_needed * BURN_RATE_PER_ENERGY
    
    # Calculate rental costs from each platform
    rental_options = []
    
    for platform in RENTAL_PLATFORMS:
        # Check minimum
        if energy_needed < platform['min_rental']:
            continue
        
        cost_per_day = (energy_needed / 1000) * platform['rate_per_1k_per_day']
        total_cost = cost_per_day * duration_days
        savings_vs_burn = burn_cost_trx - total_cost
        savings_percent = (savings_vs_burn / burn_cost_trx) * 100 if burn_cost_trx > 0 else 0
        
        rental_options.append({
            'platform': platform['name'],
            'url': platform['url'],
            'cost_trx': round(total_cost, 2),
            'cost_per_day': round(cost_per_day, 2),
            'savings_trx': round(savings_vs_burn, 2),
            'savings_percent': round(savings_percent, 1),
            'safety_rating': platform['safety'],
            'is_best': False  # Will mark later
        })
    
    # Sort by cost (cheapest first)
    rental_options.sort(key=lambda x: x['cost_trx'])
    
    # Mark best option
    if rental_options:
        rental_options[0]['is_best'] = True
    
    # Determine recommendation
    recommendation = None
    if rental_options and rental_options[0]['savings_percent'] > 20:
        recommendation = {
            'action': 'rent',
            'platform': rental_options[0]['platform'],
            'reason': f"Save {rental_options[0]['savings_percent']}% vs burning TRX"
        }
    else:
        recommendation = {
            'action': 'burn',
            'reason': 'Rental savings not significant enough'
        }
    
    return {
        'energy_needed': energy_needed,
        'duration_days': duration_days,
        'burn_cost_trx': round(burn_cost_trx, 2),
        'rental_options': rental_options,
        'recommendation': recommendation
    }

async def estimate_transaction_energy(tx_type: str) -> int:
    """
    Estimate energy requirement for common transaction types.
    
    Args:
        tx_type: Type of transaction ('usdt_transfer', 'swap', 'nft_mint', etc.)
        
    Returns:
        Estimated energy requirement
    """
    estimates = {
        'usdt_transfer': 32000,
        'trc20_transfer': 28000,
        'swap_sunswap': 65000,
        'nft_mint': 85000,
        'nft_transfer': 45000,
        'justlend_supply': 50000,
        'justlend_withdraw': 55000,
        'vote_sr': 10000,
        'unvote_sr': 10000
    }
    
    return estimates.get(tx_type.lower(), 50000)  # Default estimate
