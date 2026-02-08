"""
SR Ranking Skill
Get TRON Super Representative rankings and voting rewards comparison.
"""
import asyncio
import httpx
from typing import Dict, List, Optional
from pathlib import Path
from datetime import datetime
import sys

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from src.config import Config

TRONGRID_BASE = Config.TRONGRID_BASE

# TRON constants
BLOCKS_PER_DAY = 28800  # 3-second blocks
BLOCK_REWARD = 16  # TRX per block (for top 27 SRs)
VOTE_REWARD = 160  # TRX per day distributed to voters


async def get_sr_ranking(
    top_n: int = 10,
    sort_by: str = "voter_apy"
) -> Dict:
    """
    Get Super Representative rankings with voting rewards.
    
    Args:
        top_n: Number of top SRs to return
        sort_by: Sort criteria - voter_apy, total_votes, brokerage, uptime
        
    Returns:
        Dict with SR rankings and comparison
    """
    try:
        # Validate sort criteria
        valid_sorts = ["voter_apy", "total_votes", "brokerage", "uptime", "blocks_produced"]
        if sort_by not in valid_sorts:
            return {
                'success': False,
                'error': 'InvalidSortCriteria',
                'message': f'sort_by must be one of: {", ".join(valid_sorts)}'
            }
        
        # Fetch SR list from TronGrid
        witnesses = await _fetch_witnesses()
        
        if not witnesses:
            return {
                'success': False,
                'error': 'APIUnavailable',
                'message': 'Cannot fetch SR list from TronGrid'
            }
        
        # Process and rank witnesses
        processed = []
        total_votes = sum(w.get('voteCount', 0) for w in witnesses)
        
        for i, witness in enumerate(witnesses):
            # Calculate metrics
            votes = witness.get('voteCount', 0)
            vote_pct = (votes / total_votes * 100) if total_votes > 0 else 0
            
            brokerage = witness.get('brokerage', 20)  # Default 20%
            voter_reward_rate = 100 - brokerage
            
            # Calculate voter APY
            is_top_27 = i < 27
            voter_apy = _calculate_voter_apy(
                votes, 
                brokerage, 
                is_top_27
            )
            
            # Get additional info
            blocks_produced = witness.get('totalProduced', 0)
            blocks_missed = witness.get('totalMissed', 0)
            uptime = _calculate_uptime(blocks_produced, blocks_missed)
            
            processed.append({
                'rank': i + 1,
                'address': witness.get('address'),
                'name': witness.get('url', 'Unknown')[:50],  # SR name/URL
                'url': witness.get('url', ''),
                'total_votes': votes,
                'vote_percentage': round(vote_pct, 2),
                'brokerage': brokerage,
                'voter_reward_rate': voter_reward_rate,
                'voter_apy': round(voter_apy, 2),
                'blocks_produced': blocks_produced,
                'blocks_missed': blocks_missed,
                'uptime': round(uptime, 3),
                'is_top_27': is_top_27,
                'last_update': datetime.now().isoformat()
            })
        
        # Sort by criteria
        sort_key_map = {
            'voter_apy': lambda x: x['voter_apy'],
            'total_votes': lambda x: x['total_votes'],
            'brokerage': lambda x: -x['brokerage'],  # Lower is better
            'uptime': lambda x: x['uptime'],
            'blocks_produced': lambda x: x['blocks_produced']
        }
        
        processed.sort(key=sort_key_map[sort_by], reverse=True)
        
        # Get top N
        top_srs = processed[:top_n]
        
        # Calculate summary stats
        summary = {
            'avg_voter_apy': round(sum(sr['voter_apy'] for sr in top_srs) / len(top_srs), 2),
            'highest_apy': max(sr['voter_apy'] for sr in top_srs),
            'lowest_brokerage': min(sr['brokerage'] for sr in top_srs),
            'most_voted': max(top_srs, key=lambda x: x['total_votes'])['name']
        }
        
        # Generate recommendations
        best_apy_sr = max(top_srs, key=lambda x: x['voter_apy'])
        most_voted_sr = max(top_srs, key=lambda x: x['total_votes'])
        lowest_brokerage_sr = min(top_srs, key=lambda x: x['brokerage'])
        
        recommendations = [
            f"🏆 Best APY: {best_apy_sr['name'][:20]} ({best_apy_sr['voter_apy']}%)",
            f"📊 Most voted: {most_voted_sr['name'][:20]} ({most_voted_sr['vote_percentage']}% of total)",
            f"💰 Lowest brokerage: {lowest_brokerage_sr['name'][:20]} ({lowest_brokerage_sr['brokerage']}%)"
        ]
        
        return {
            'success': True,
            'message': f'Retrieved top {top_n} Super Representatives',
            'data': {
                'total_srs': len(processed),
                'top_srs': 27,
                'update_time': datetime.now().isoformat(),
                'sort_by': sort_by,
                'rankings': top_srs,
                'summary': summary
            },
            'recommendations': recommendations
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to get SR rankings: {str(e)}'
        }


async def simulate_voting_rewards(
    sr_address: str,
    vote_amount: int
) -> Dict:
    """
    Simulate voting rewards for a specific SR.
    
    Args:
        sr_address: SR address to vote for
        vote_amount: Amount of TRX to vote with
        
    Returns:
        Estimated rewards (daily, monthly, annual)
    """
    try:
        # Get SR info
        witnesses = await _fetch_witnesses()
        sr = next((w for w in witnesses if w['address'] == sr_address), None)
        
        if not sr:
            return {
                'success': False,
                'error': 'SRNotFound',
                'message': f'SR {sr_address} not found'
            }
        
        # Calculate rewards
        brokerage = sr.get('brokerage', 20)
        voter_reward_rate = (100 - brokerage) / 100
        
        # Simple estimation (actual calculation is complex)
        total_votes = sr.get('voteCount', 1)
        vote_share = vote_amount / (total_votes + vote_amount)
        
        # Daily rewards estimation
        is_top_27 = witnesses.index(sr) < 27
        if is_top_27:
            # Top 27 get block rewards + vote rewards
            daily_block_rewards = BLOCK_REWARD * BLOCKS_PER_DAY
            daily_vote_rewards = VOTE_REWARD
            total_daily = (daily_block_rewards + daily_vote_rewards) * voter_reward_rate
        else:
            # Standby SRs only get vote rewards
            total_daily = VOTE_REWARD * voter_reward_rate
        
        daily_trx = total_daily * vote_share
        monthly_trx = daily_trx * 30
        annual_trx = daily_trx * 365
        apy = (annual_trx / vote_amount) * 100
        
        return {
            'success': True,
            'message': f'Estimated rewards for voting {vote_amount} TRX',
            'data': {
                'sr_name': sr.get('url', 'Unknown'),
                'sr_address': sr_address,
                'vote_amount': vote_amount,
                'brokerage': brokerage,
                'voter_reward_rate': 100 - brokerage,
                'is_top_27': is_top_27,
                'daily_trx': round(daily_trx, 2),
                'monthly_trx': round(monthly_trx, 2),
                'annual_trx': round(annual_trx, 2),
                'apy': round(apy, 2)
            }
        }
    
    except Exception as e:
        return {
            'success': False,
            'error': str(e),
            'message': f'Failed to simulate voting rewards: {str(e)}'
        }


async def _fetch_witnesses() -> List[Dict]:
    """Fetch witness/SR list from TronGrid."""
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(
                f"{TRONGRID_BASE}/wallet/listwitnesses"
            )
            
            if response.status_code == 200:
                data = response.json()
                return data.get('witnesses', [])
    except Exception as e:
        print(f"Error fetching witnesses: {e}")
    
    return []


def _calculate_voter_apy(votes: int, brokerage: int, is_top_27: bool) -> float:
    """
    Calculate estimated APY for voters.
    
    Simplified calculation - actual APY varies based on many factors.
    """
    if votes == 0:
        return 0.0
    
    voter_reward_rate = (100 - brokerage) / 100
    
    if is_top_27:
        # Top 27 produce blocks and get rewards
        # Rough estimation: ~4-5% APY for top SRs
        base_apy = 5.0
    else:
        # Standby SRs get less
        base_apy = 2.0
    
    # Adjust for brokerage
    adjusted_apy = base_apy * voter_reward_rate
    
    return adjusted_apy


def _calculate_uptime(blocks_produced: int, blocks_missed: int) -> float:
    """Calculate SR uptime percentage."""
    if blocks_produced + blocks_missed == 0:
        return 100.0
    
    total = blocks_produced + blocks_missed
    uptime = (blocks_produced / total) * 100
    
    return uptime


# For testing
if __name__ == "__main__":
    async def test():
        # Test getting top SRs
        result = await get_sr_ranking(top_n=5, sort_by="voter_apy")
        
        print("=" * 80)
        print("TRON Super Representative Rankings")
        print("=" * 80)
        
        if result['success']:
            for sr in result['data']['rankings']:
                print(f"\n#{sr['rank']} {sr['name'][:30]}")
                print(f"  Votes: {sr['total_votes']:,} ({sr['vote_percentage']}%)")
                print(f"  Voter APY: {sr['voter_apy']}%")
                print(f"  Brokerage: {sr['brokerage']}% (voters get {sr['voter_reward_rate']}%)")
                print(f"  Uptime: {sr['uptime']}%")
                print(f"  Status: {'✅ Top 27' if sr['is_top_27'] else '⏸️ Standby'}")
            
            print("\n" + "=" * 80)
            print("Recommendations:")
            for rec in result['recommendations']:
                print(f"  {rec}")
        else:
            print(f"Error: {result['error']}")
            print(f"Message: {result['message']}")
    
    asyncio.run(test())
