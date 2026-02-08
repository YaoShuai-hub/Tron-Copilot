---
name: token-price
description: Get real-time and historical cryptocurrency prices for TRON ecosystem tokens (TRX, USDT, BTT, etc.) from multiple sources including Binance, CoinGecko, and DEX aggregators.
---

# Token Price Skill

## When to use this skill

Use this skill when the user needs to:
- Check current prices of TRON tokens
- Compare prices across multiple exchanges
- View price trends or changes
- Get USD valuations for portfolio calculations

## Supported tokens

- **Major tokens**: TRX, USDT (TRC20), USDD, BTT, JST, SUN, NFT
- **Any TRC20 token**: By contract address

## Data sources

1. **Binance API**: Most reliable for major tokens (TRX, BTC, ETH)
2. **CoinGecko**: Comprehensive crypto data
3. **SunSwap**: On-chain TRON DEX prices
4. **DexScreener**: Multi-DEX aggregator

## How to fetch a token price

```python
from skills.token_price.scripts.fetch_price import get_token_price

# By symbol
price = await get_token_price("TRX")
# Returns: {"symbol": "TRX", "usd_price": 0.23, "source": "binance", "timestamp": ...}

# By contract address
price = await get_token_price("TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t")
```

## Error handling

- Returns `0.0` if price not found
- Automatically falls back across data sources
- Caches prices for 30 seconds to avoid rate limits

## Output format

Human-readable when called via MCP:
```
💰 TRX Price: $0.2345 USD
📊 24h Change: +5.2%
🔍 Source: Binance
⏰ Updated: 2 seconds ago
```

## Rate limits

- Binance: 1200 requests/minute (no key needed)
- CoinGecko: 50 calls/minute (free tier)
- On-chain: Limited by TronGrid API key
