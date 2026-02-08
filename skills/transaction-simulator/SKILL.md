---
name: transaction-simulator
description: Simulate transactions before execution to preview outcomes and detect failures. Save gas and prevent errors.
---

# Transaction Simulator

## When to use this skill

Use this skill **BEFORE** executing:
- Complex swaps or trades
- Smart contract interactions
- Large transfers
- DeFi operations (stake, lend, etc.)

## What It Does

Simulates your transaction on a **test environment** to show:
- ✅ Will it succeed or fail?
- 📊 Expected output amounts
- 💰 Actual gas costs
- ⚠️ Warnings and errors
- 🔄 State changes preview

**NO REAL TRANSACTION IS SENT** - It's a safe preview!

## Benefits

### 💰 Save Money
- Avoid failed transactions (still cost gas!)
- Preview slippage before swapping
- Verify gas estimates

### 🛡️ Prevent Errors
- Catch insufficient balance
- Detect approval issues
- Identify smart contract bugs

### 📊 Better Planning
- See exact output amounts
- Preview price impact
- Understand state changes

## Usage

```python
from skills.transaction_simulator.scripts.simulate_tx import simulate_transaction

# Simulate a swap
tx_data = {
    'from': 'TXXXabc...',
    'to': 'SunSwap_Router',
    'value': 100,
    'data': '...'  # Transaction data
}

result = await simulate_transaction(tx_data)

if result['success']:
    print(f"Expected output: {result['output_amount']}")
    print(f"Gas cost: {result['gas_used']}")
else:
    print(f"Would fail: {result['error']}")
```

## Output Example

### ✅ Successful Simulation

```
🎮 Transaction Simulation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Operation: Swap 100 TRX → USDT
Simulation: ✅ SUCCESS

Expected Results:
  • Output: 14.85 USDT
  • Price: 1 TRX = 0.1485 USDT
  • Slippage: 0.5%
  • Price Impact: 0.02%

Costs:
  • Gas Used: ~50,000 Energy
  • Est. Fee: 0.15 TRX

⏱️ Simulation Time: 1.2s

✅ Transaction will succeed
💡 Proceed with confidence!
```

### ❌ Failed Simulation

```
🎮 Transaction Simulation
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Operation: Swap 1000 TRX → SCAM_TOKEN

Simulation: ❌ FAILED

Error: "Transfer failed - Honeypot detected"

Details:
  • Cannot sell this token after buying
  • Contract has blacklist function
  • Sell tax: 99%

🚨 DO NOT EXECUTE THIS TRANSACTION!

Saved you: ~1000 TRX + gas fees
```

## Technical Details

### Simulation Methods

1. **TronGrid Simulation API** (if available)
   - Most accurate
   - Uses actual blockchain state
   
2. **Local Fork Simulation**
   - Creates temporary blockchain fork
   - Executes transaction locally
   
3. **Bytecode Analysis**
   - Analyzes contract code
   - Predicts execution flow

### Limitations

- ⚠️ Simulations use **current** blockchain state
- 🕐 Actual execution may differ if state changes
- 🔄 Time-sensitive operations may behave differently
- 📊 Gas estimates are approximate

## Integration

Should auto-run before:
- Any swap >$100 USD value
- User's first interaction with a contract
- Transactions to unverified contracts
- User explicitly requests simulation

## Safety

✅ **100% Safe** - No real transactions sent
✅ **No costs** - Simulation is free
✅ **Privacy** - Simulations run locally when possible
