---
name: transfer-tokens
description: Build unsigned transactions for transferring TRX or TRC20 tokens (USDT, USDD, etc.) to another address with amount validation and energy estimation.
---

# Transfer Tokens Skill

## When to use this skill

Use this skill when the user wants to:
- Send TRX to another wallet
- Transfer TRC20 tokens (USDT, USDD, BTT, etc.)
- Send tokens with memo/note
- Check transfer costs before sending

## Security features

🔒 **Never handles private keys**
- Generates UNSIGNED transactions only
- User signs in their own wallet (TronLink, etc.)
- Pre-validates sufficient balance
- Energy cost estimation

## Supported transfers

- **TRX**: Native TRON token
- **TRC20 tokens**: USDT, USDD, BTT, JST, and any TRC20 contract
- Auto-detects token type by address

## How it works

1. **Validation**: Check sender has sufficient balance
2. **Energy estimation**: Calculate required energy
3. **Transaction build**: Create unsigned transaction JSON
4. **Safety check**: Warn if energy/bandwidth insufficient

## Usage

```python
from skills.transfer_tokens.scripts.build_transfer import build_transfer_transaction

tx = await build_transfer_transaction(
    from_address="TYourAddress...",
    to_address="TRecipient...",
    token="TRX",  # or TRC20 contract address
    amount=10.5,
    memo="Payment for services"
)
```

## Parameters

- **from_address**: Sender wallet address (tx signer)
- **to_address**: Recipient wallet address
- **token**: "TRX" or TRC20 contract address (e.g., "TR7N..." for USDT)
- **amount**: Amount to transfer (in token decimals)
- **memo**: Optional memo/note (only for TRX transfers)

## Output

Returns unsigned transaction JSON:
```json
{
  "txID": "...",
  "raw_data": {
    "contract": [{
      "parameter": {
        "value": {
          "amount": 10500000,
          "to_address": "...",
          "owner_address": "..."
        }
      }
    }]
  },
  "metadata": {
    "token": "TRX",
    "amount": 10.5,
    "recipient": "TRecipient...",
    "estimated_energy": 0,
    "estimated_bandwidth": 270
  }
}
```

## Important safety checks

⚠️ **Before signing:**
1. ✅ Verify recipient address (double-check!)
2. ✅ Confirm amount (decimal places matter!)
3. ✅ Check you have enough TRX for energy/bandwidth
4. ✅ For USDT transfers: ~14,000-32,000 Energy needed

## Energy costs

| Transfer Type | Energy | Bandwidth | Typical Cost |
|--------------|--------|-----------|--------------|
| TRX          | 0      | ~270      | FREE (if bandwidth available) |
| TRC20 (USDT) | 14,000-32,000 | ~350 | ~0.5-1.5 TRX (or rent energy!) |

💡 **Tip**: For USDT transfers, use the `energy-rental` skill first to save 70% on fees!
