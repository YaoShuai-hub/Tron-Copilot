---
name: energy-rental
description: Analyze energy costs for TRON transactions and generate rental proposals to save on fees. Compares burning TRX vs renting energy from platforms.
---

# Energy Rental Skill

## When to use this skill

Use this skill when the user needs to:
- Save on TRON transaction fees
- Execute energy-intensive operations (token transfers, smart contracts)
- Compare energy costs across different options
- Get rental proposals from energy marketplaces

## TRON Energy Basics

TRON transactions consume **Energy** and **Bandwidth**:
- **Bandwidth**: Free (1500/day regenerates)
- **Energy**: Costly (burns TRX if you don't have enough)

### Typical energy costs:
- USDT transfer: ~14,000 - 32,000 Energy
- Smart contract call: 10,000 - 100,000 Energy
- Complex DeFi: 100,000+ Energy

### Options:
1. **Burn TRX**: ~420 sun per Energy (~0.000420 TRX)
2. **Stake TRX**: Lock 1 TRX = ~1,000 Energy/day
3. **Rent Energy**: Pay ~100-200 sun per Energy (70% cheaper!)

## How to get rental proposal

```python
from skills.energy_rental.scripts.calculate_rental import get_rental_proposal

proposal = await get_rental_proposal(
    energy_needed=32000,
    duration_days=3
)
```

## Output format

```
⚡ Energy Rental Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Transaction needs: 32,000 Energy

💰 Cost Comparison:
  Option A - Burn TRX:  13.44 TRX
  Option B - Rent (3d): 3.84 TRX  ✅ Save 71%!

📊 Rental Options:
  1. JustLend DAO    - 0.12 TRX/1K energy/day
  2. Justmoney Club  - 0.10 TRX/1K energy/day  ⭐ Best
  3. Stake.Energy    - 0.15 TRX/1K energy/day

⚡ Recommended: Rent from Justmoney Club
💵 Total cost: 3.84 TRX for 3 days
```

## Rental platforms

1. **JustLend DAO**: Official, safe, slightly expensive
2. **Justmoney.club**: Community favorite, best rates
3. **Stake.energy**: Alternative option
4. **Nicetron.cc**: Bulk rentals

## Important notes

⚠️ **Energy rental tips:**
- Rent slightly more than estimated (buffer)
- Longer duration = better rate usually
- Check platform's minimum rental
- Energy is consumed on use, not time

## Smart recommendations

The skill analyzes:
- Current TRX burn rate
- Available rental platforms
- Transaction urgency
- Cost-benefit analysis

Auto-recommends best option based on savings threshold (>20%).
