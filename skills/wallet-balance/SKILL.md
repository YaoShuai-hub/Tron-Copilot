---
name: wallet-balance
description: Get comprehensive portfolio view of TRON wallet including all token balances, USD valuations, and portfolio composition analysis.
---

# Wallet Balance Skill

## When to use this skill

Use this skill when the user needs to:
- Check their wallet balance
- View complete portfolio (all tokens)
- Get USD valuations of holdings
- Analyze portfolio composition
- Monitor specific addresses

## Features

### Multi-token support
- TRX (native token)
- All TRC20 tokens (USDT, USDD, BTT, etc.)
- TRC10 tokens
- Automatic token detection

### Portfolio analysis
- Total portfolio value in USD
- Individual token valuations
- Percentage composition
- Top holdings

### Data sources
- TronScan API for aggregated token data
- TronGrid for on-chain verification
- Price data from token-price skill

## How to check wallet balance

```python
from skills.wallet_balance.scripts.get_balance import get_wallet_balance

result = await get_wallet_balance("TKzxdSv2FZKQrEqkKVgp5DcwEXBEKMg2Ax")
```

## Output format

```
💰 Wallet Portfolio: TKzx...Mg2Ax
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Total Value: $12,345.67 USD

Assets:
  1. 5,000 USDT  → $5,000.00 (40.5%)
  2. 20,000 TRX  → $4,600.00 (37.2%)
  3. 1,000,000 BTT → $2,500.00 (20.3%)
  4. 100 USDD    → $100.00   (0.8%)

🔗 View on TronScan: https://tronscan.org/#/address/...
⏰ Updated: Just now
```

## Address validation

- Checks for valid TRON address format (starts with T, 34 chars)
- Verifies Base58 encoding
- Returns error for invalid addresses

## Performance

- Typical response time: 1-2 seconds
- Caches token metadata
- Parallel price fetching for multiple tokens
