---
name: swap-tokens
description: Build secure unsigned transactions for token swaps on SunSwap DEX with automatic path finding, slippage protection, and transaction validation.
---

# Swap Tokens Skill

## When to use this skill

Use this skill when the user wants to:
- Swap tokens on SunSwap DEX
- Exchange TRX for TRC20 tokens
- Trade between TRC20 tokens
- Get best swap routes

## Security features

🔒 **Never handles private keys**
- Generates UNSIGNED transactions only
- User signs in their own wallet (TronLink, etc.)
- Pre-execution simulation available

## Supported swaps

- TRX ↔ TRC20 tokens
- TRC20 ↔ TRC20 (via TRX pairs)
- Automatic path finding for best rates

## How it works

1. **Path finding**: Determine optimal swap route
2. **Amount calculation**: Query on-chain reserves for exact output
3. **Transaction build**: Create unsigned transaction JSON
4. **Validation**: Simulate before signing

## Usage

```python
from skills.swap_tokens.scripts.build_swap import build_swap_transaction

tx = await build_swap_transaction(
    user_address="TYourAddress...",
    token_in="TRX",
    token_out="TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t",  # USDT
    amount_in=100,
    slippage=0.5
)
```

## Parameters

- **user_address**: Your wallet address (tx signer)
- **token_in**: Symbol (e.g., "TRX") or contract address
- **token_out**: Symbol or contract address
- **amount_in**: Amount to swap (in token decimals)
- **slippage**: Max acceptable slippage (%) default 0.5%

## Output

Returns unsigned transaction JSON:
```json
{
  "txID": "...",
  "raw_data": {
    "contract": [...],
    "fee_limit": 100000000
  },
  "visible": true,
  "metadata": {
    "expected_output": "99.5 USDT",
    "minimum_output": "99.0 USDT",
    "price_impact": "0.12%",
    "path": ["TRX", "WTRX", "USDT"]
  }
}
```

## Important notes

⚠️ **Before signing:**
1. Review expected output amount
2. Check price impact
3. Verify contract addresses
4. Ensure sufficient TRX for energy/bandwidth

## Smart features

- **Approval detection**: Checks if token approval needed
- **Energy estimation**: Predicts energy cost
- **Path optimization**: Finds best route (direct vs multi-hop)
- **Slippage protection**: Sets minimum output
